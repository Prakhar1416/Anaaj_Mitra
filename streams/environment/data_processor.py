"""Prepare clearly labelled CGWB-real and synthetic records for the project."""
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent
REAL=ROOT/"data/raw/real/cgwb_groundwater_jan2025.csv"
SYN=ROOT/"data/raw/synthetic/synthetic_villages.csv"
OUT=ROOT/"data/processed/environmental_hybrid.csv"

def process_data():
    frames=[]
    if REAL.exists():
        g=pd.read_csv(REAL)
        g["data_source"]="REAL_CGWB"
        g["record_type"]="Groundwater observation"
        frames.append(g)
    if SYN.exists():
        s=pd.read_csv(SYN)
        s["data_source"]="SYNTHETIC"
        s["record_type"]="Synthetic demo observation"
        frames.append(s)
    if not frames:
        raise FileNotFoundError("No real CGWB or synthetic input CSV found")
    combined=pd.concat(frames,ignore_index=True,sort=False)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    combined.to_csv(OUT,index=False)
    print(f"Saved {len(combined):,} rows to {OUT}")
    print("Rows by source:")
    print(combined["data_source"].value_counts().to_string())
    return combined

if __name__=="__main__": process_data()
