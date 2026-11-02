"""Run the frozen graph LOFO protocol with five reproducible seeds."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--cohort',choices=['all','yosys_verilog','mapped'],default='all')
    parser.add_argument('--features',choices=['raw','scaled','no_proxies','topology_only'],default='raw')
    parser.add_argument('--weighting',choices=['source_balanced','record_balanced'],default='source_balanced')
    parser.add_argument('--manifest',default='data/lofo_detection/protocol.json')
    args=parser.parse_args()
    for seed in (42,43,44,45,46):
        cmd=[sys.executable,'-u','pipeline/train_lofo.py','--seed',str(seed),'--features',args.features,
             '--weighting',args.weighting,'--cohort',args.cohort,'--manifest',args.manifest]
        subprocess.run(cmd,cwd=ROOT,check=True)
