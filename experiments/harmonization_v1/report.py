"""Publish a compact, explicitly scoped pilot report after all stages finish."""
import json
from pilot import ROOT, OUT, digest


def main():
    rows=[]
    for benchmark in ['RS232-T2100','AES-T100']:
        for side in ['clean','trojan']:
            folder=OUT/benchmark/side
            status=json.loads((folder/'status.json').read_text())
            assert digest(ROOT/status['input_json'])==status['input_sha256']
            if 'output_sha256' in status:
                assert digest(folder/'yosys.json')==status['output_sha256']
                status['yosys_creator']=json.loads((folder/'yosys.json').read_text()).get('creator')
            for path,expected in status['source_hashes'].items():
                assert digest(ROOT/path)==expected
            rows.append(status)
    rom=json.loads((OUT/'rom_validation.json').read_text())
    for record in rom['records']:
        folder=OUT/'rom_validation'/record['side']
        if 'mapped_sha256' in record:
            assert digest(folder/f'{record["unit"]}_mapped.v')==record['mapped_sha256']
            assert digest(folder/f'{record["unit"]}_test.v')==record['bench_sha256']
    inventory=json.loads((OUT/'library_inventory.json').read_text())
    summary=dict(version='harmonization_v1', status='completed_pilot_with_scoped_validation',
                 whole_design_memory_equivalence='not_independently_established',
                 training_eligible=False,
                 pilot=rows,rom_validation=rom,library_inventory=inventory)
    destination=ROOT/'experiments/harmonization_v1/results'
    destination.mkdir(exist_ok=True)
    (destination/'summary.json').write_text(json.dumps(summary,indent=2))
    (OUT/'pilot_summary.json').write_text(json.dumps(rows,indent=2))
    print(json.dumps([dict(benchmark=r['benchmark'],side=r['side'],
                          nodes=r.get('graph_verification',{}).get('nodes'),
                          growth=r.get('node_growth_ratio'),
                          proof=r.get('post_lowering_equivalence')) for r in rows],indent=2))


if __name__=='__main__':
    main()
