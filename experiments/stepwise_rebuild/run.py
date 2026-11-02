"""Reproduce one or all stages in this worktree using the current Python environment.

Install requirements-lock.txt first. Outputs are written only below runs/.
Re-running a stage overwrites its corresponding outputs. Model download is
an explicit stage and requires network access; embeddings use the local cache.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'runs/stepwise'
STAGES=['download','build','audit','gnn','embed','compare','hosts','external','report']


def execute(name,script,*args):
    target=OUT/'logs'/f'{name}.log';target.parent.mkdir(parents=True,exist_ok=True)
    print(f'{name}: {script} {" ".join(args)}',flush=True)
    with target.open('w') as log:
        subprocess.run([sys.executable,'-u',script,*args],cwd=ROOT,env=ENV,stdout=log,stderr=subprocess.STDOUT,check=True)


ENV=dict(os.environ,HT_RUNS_ROOT=str(OUT),HF_HOME=str(OUT/'hf_cache'),XDG_CACHE_HOME=str(OUT/'cache'),OMP_NUM_THREADS='4',MKL_NUM_THREADS='4')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['all',*STAGES],required=True)
    args=parser.parse_args()
    for stage in STAGES if args.stage=='all' else [args.stage]:
        if stage=='download':
            execute('download-codebert','-c',"from huggingface_hub import snapshot_download; snapshot_download('microsoft/codebert-base', revision='3b0952feddeffad0063f274080e3c23d75e7eb39', allow_patterns=['config.json','vocab.json','merges.txt','tokenizer*','special_tokens_map.json','pytorch_model.bin'])")
        elif stage=='build':
            import shutil
            yosys=Path(sys.executable).parent/'yowasp-yosys'
            execute('prepare-memctrl','pipeline/provenance/prepare_memctrl.py')
            extractor=shutil.which('bsdtar')
            execute('prepare-pic','pipeline/provenance/prepare_pic.py',*(['--bsdtar',extractor] if extractor else []))
            execute('build','pipeline/provenance/build.py','--all-paired','--yosys',str(yosys))
            execute('build-memctrl','pipeline/provenance/build.py','--benchmark','memctrl-T100','--out','runs/expansion_graphs','--yosys',str(yosys))
            execute('build-pic','pipeline/provenance/build.py',*[v for n in [100,200,300,400] for v in ['--benchmark',f'PIC16F84-T{n}']],'--out','runs/expansion_pic_graphs','--yosys',str(yosys))
        elif stage=='audit':
            for name,folder in [('graphs','provenance_v1'),('memctrl','expansion_graphs'),('pic','expansion_pic_graphs')]:
                execute(f'verify-{name}','pipeline/provenance/verify.py',f'runs/{folder}')
                execute(f'completeness-{name}','pipeline/provenance/audit_completeness.py',f'runs/{folder}')
            execute('tests','-m','unittest','discover','-s','pipeline/tests')
        elif stage=='gnn':
            execute('rebuilt-gnn','pipeline/train_cv.py','--model','gnn','--dataset','provenance','--epochs','25','--tag','rebuilt_gnn')
        elif stage=='embed':
            execute('embed-rtl','pipeline/provenance/embed_rtl.py')
            execute('verify-rtl','pipeline/provenance/verify_rtl.py')
            execute('embed-expansion','pipeline/provenance/embed_rtl.py','--expansion-only')
            execute('verify-expansion-rtl','pipeline/provenance/verify_rtl.py','--expansion')
        elif stage=='compare':
            for model in ['rtl','fusion']:
                execute(f'clean-{model}','pipeline/train_cv.py','--model',model,'--dataset','provenance_clean','--epochs','25','--tag',f'clean_{model}')
            execute('length-control','pipeline/length_baseline.py')
            execute('size-control','pipeline/length_baseline.py','--graph-size')
        elif stage=='hosts':
            execute('host-study','experiments/stepwise_rebuild/host_study.py')
        elif stage=='external':
            for model in ['gnn','rtl','fusion','length']:
                execute(f'external-{model}','pipeline/train_external.py','--model',model,'--epochs','25')
        elif stage=='report':
            execute('calibration','experiments/stepwise_rebuild/calibrate.py')
            execute('report','experiments/stepwise_rebuild/report.py')


if __name__=='__main__':main()
