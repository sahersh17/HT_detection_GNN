"""Remove attack labels from model text and rebuild only changed frozen embeddings."""
import hashlib,json,re,sys
from pathlib import Path
import torch
from transformers import AutoModel,AutoTokenizer

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"experiments/rtl_lexical_v1"))
from prepare import TOKEN,IDENT
RUN=ROOT/"runs/training_audit_v3"
OUT=ROOT/"data/training_audit_v3"
REVISION="3b0952feddeffad0063f274080e3c23d75e7eb39"
FORBIDDEN=re.compile(r"trojan|tjfree|tjin|infected|malicious",re.I)

def sanitize(text):
    parts=[]
    for token in TOKEN.findall(text):
        if not FORBIDDEN.search(token):
            parts.append(token)
        elif token.startswith(("//","/*")):
            parts.append("".join("\n" if c=="\n" else " " for c in token))
        elif IDENT.fullmatch(token) or token.startswith("\\"):
            prefix="\\" if token.startswith("\\") else ""
            parts.append(prefix+"signal_"+hashlib.sha256(token.encode()).hexdigest()[:12])
        else:
            parts.append(FORBIDDEN.sub("event",token))
    result="".join(parts)
    if FORBIDDEN.search(result):
        raise ValueError("Attack wording remains")
    return result

def text_for(record):
    for name, expected in record["source_sha256"].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Source hash changed: {name}")
    return "\n\n".join((ROOT/name).read_text(errors="replace").replace("\r\n","\n")
                       for name in sorted(record["source_sha256"]) if name.endswith(".v"))

def tokenize(tokenizer,text):
    encoded=tokenizer(text,truncation=True,max_length=512,stride=50,return_overflowing_tokens=True,padding="max_length")
    return [tuple(ids) for ids in encoded["input_ids"]]

def main():
    torch.set_num_threads(4)
    source=json.loads((ROOT/"data/augmentation_v2/manifest.json").read_text())
    tokenizer=AutoTokenizer.from_pretrained("microsoft/codebert-base",revision=REVISION,local_files_only=True)
    encoder=AutoModel.from_pretrained("microsoft/codebert-base",revision=REVISION,local_files_only=True).eval()
    destination=RUN/"prepared";destination.mkdir(exist_ok=True)
    previous_path = OUT/"manifest.json"
    previous = {}
    if previous_path.exists():
        previous = {row["key"]: row for row in json.loads(previous_path.read_bytes())["records"]}
    chunks={}
    for row in source["records"]:
        item=torch.load(ROOT/row["file"],weights_only=False)
        keys=tokenize(tokenizer,text_for(row))
        if len(keys)!=len(item["rtl"]):raise ValueError(row["key"])
        for key,value in zip(keys,item["rtl"]):
            chunks.setdefault(key,value.clone())
    records=[]
    for index,row in enumerate(source["records"]):
        path=destination/(row["key"]+".pt")
        raw=text_for(row);cleaned=sanitize(raw)
        text_hash = hashlib.sha256(cleaned.encode()).hexdigest()
        source_path=destination/(row["key"]+".v")
        source_path.write_text(cleaned)
        old = previous.get(row["key"], {})
        cache_valid = (path.exists() and old.get("sanitized_text_sha256") == text_hash
                       and hashlib.sha256(path.read_bytes()).hexdigest() == old.get("sha256"))
        if not cache_valid:
            item=torch.load(ROOT/row["file"],weights_only=False)
            keys=tokenize(tokenizer,cleaned)
            missing=list(dict.fromkeys(key for key in keys if key not in chunks))
            with torch.inference_mode():
                for start in range(0,len(missing),8):
                    batch=missing[start:start+8]
                    ids=torch.tensor(batch)
                    mask=(ids!=tokenizer.pad_token_id).long()
                    hidden=encoder(input_ids=ids,attention_mask=mask).last_hidden_state
                    weight=mask.unsqueeze(-1).to(hidden.dtype)
                    vectors=(hidden*weight).sum(1)/weight.sum(1).clamp(min=1)
                    for key,value in zip(batch,vectors):chunks[key]=value.cpu().clone()
            item["rtl"]=torch.stack([chunks[key] for key in keys])
            torch.save(item,path)
        records.append(dict(row,file=path.relative_to(ROOT).as_posix(),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            wording_occurrences_removed=len(FORBIDDEN.findall(raw)),
            sanitized_text_sha256=text_hash))
        print(index+1,len(source["records"]),row["key"],records[-1]["wording_occurrences_removed"],flush=True)
    (OUT/"manifest.json").write_text(json.dumps(dict(records=records,model_revision=REVISION,
        sanitized_terms=FORBIDDEN.pattern,graphs_unchanged=True),indent=2))
if __name__=="__main__":
    main()
