"""Generate labelled synthetic village records for testing only."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"data/raw/synthetic/synthetic_villages.csv"
def generate(records=1000,seed=42):
    rng=np.random.default_rng(seed)
    districts=["Bhopal","Indore","Vidisha","Rewa","Mandla","Datia"]
    soils=["Sandy","Loamy","Clayey","Alluvial"]
    df=pd.DataFrame({"village_id":[f"SYN_V{i:05d}" for i in range(1,records+1)],
        "district":rng.choice(districts,records),"month":rng.integers(1,13,records),
        "rainfall_mm_annual":rng.uniform(500,1800,records).round(1),
        "groundwater_depth_m_bgl":rng.uniform(1,25,records).round(2),
        "soil_type":rng.choice(soils,records),"data_source":"SYNTHETIC"})
    OUT.parent.mkdir(parents=True,exist_ok=True); df.to_csv(OUT,index=False)
    print(f"Generated {len(df)} SYNTHETIC records: {OUT}")
    return df
if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--records",type=int,default=1000); p.add_argument("--seed",type=int,default=42); a=p.parse_args(); generate(a.records,a.seed)
