"""Independent Icarus comparison of source AES ROM units and lowered units."""
import json
import subprocess
from pathlib import Path
import shutil
from pilot import ROOT, OUT, execute, relative, digest


def main():
    rows=[]
    for side,tag in [('clean','TjFree'),('trojan','TjIn')]:
        source=ROOT/f'trusthub/AES_unzipped/AES-T100/AES-T100/src/{tag}/table.v'
        target=OUT/'rom_validation'/side
        target.mkdir(parents=True,exist_ok=True)
        for unit in ['S','xS']:
            mapped=target/f'{unit}_mapped.v'
            script=f'read_verilog {relative(source)}\nhierarchy -check -top {unit}\nproc\nopt\nflatten\nmemory_collect\nmemory_map\nopt\ntechmap\nopt\nrename {unit} mapped_{unit}\nwrite_verilog -noattr {relative(mapped)}\n'
            status=execute(script,target,unit)
            record=dict(side=side,unit=unit,source_sha256=digest(source),conversion=status)
            if status['returncode']==0:
                bench=target/f'{unit}_test.v'
                bench.write_text(f'''module tb;
reg clk=0; reg [7:0] addr=0;
wire [7:0] original, mapped;
{unit} reference(clk,addr,original);
mapped_{unit} candidate(clk,addr,mapped);
integer i; reg [7:0] previous;
initial begin
  for(i=0;i<256;i=i+1) begin
    clk=0; addr=i; #2; clk=1; #2;
    if(original !== mapped) $fatal(1,"ROM mismatch address %d",i);
    previous=mapped; clk=0; addr=255-i; #2;
    if(mapped !== previous || original !== previous) $fatal(1,"Clock hold mismatch");
  end
  $display("PASS 256 addresses and clock-hold checks"); $finish;
end
endmodule
''')
                binary=target/f'{unit}.vvp'
                wrapper=ROOT/'experiments/harmonization_v1/simulate.ps1'
                status_path=target/f'{unit}_simulation_status.json'
                status_path.write_text(json.dumps(dict(passed=False,status='not_completed')))
                simulation_run=subprocess.run([shutil.which('pwsh') or 'powershell','-NoProfile','-File',str(wrapper),'-Side',side,'-Unit',unit],cwd=ROOT,timeout=120,check=False)
                record.update(json.loads(status_path.read_text(encoding='utf-8-sig')))
                if simulation_run.returncode:
                    record['passed']=False
                record.update(mapped_sha256=digest(mapped),bench_sha256=digest(bench))
            rows.append(record)
            print(json.dumps(record),flush=True)
    (OUT/'rom_validation.json').write_text(json.dumps(dict(scope='Exhaustive binary addresses and clock holds of S/xS units; not whole-AES formal equivalence or X-state proof',records=rows),indent=2))


if __name__=='__main__':
    main()
