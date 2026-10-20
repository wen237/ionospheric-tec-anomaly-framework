from datetime import date
import numpy as np
import pytest
from scripts.validation.gim.validate_16days import select_pairs


def write_day(old_dir, new_dir, day, *, bad_boundary=False):
    from datetime import datetime, timedelta
    base=datetime.combine(day, datetime.min.time())
    times=np.array([[*(base+timedelta(hours=h)).timetuple()[:6]] for h in range(25)])
    raw=np.full((25,71,73), 123, dtype=np.int32)
    raw[0,0,0]=0
    raw[1,1,1]=9999
    if bad_boundary:
        raw[24,:,:]=700  # Must never become next day's hour 00.
    lp=old_dir/f'legacy_{day}.npz'
    mp=new_dir/f'modern_{day}.npz'
    np.savez_compressed(lp,gim=raw.reshape(-1,73),gim_time=times,gim_lat=np.linspace(87.5,-87.5,71),gim_lon=np.linspace(-180,180,73))
    tec=raw.astype(float)/10
    tec[(raw==0)|(raw==9999)]=np.nan
    epochs=np.array([np.datetime64(base,'s')+np.timedelta64(h,'h') for h in range(25)])
    np.savez_compressed(mp,tec=tec,epochs=epochs,lat=np.linspace(87.5,-87.5,71),lon=np.linspace(-180,180,73))
    return lp,mp


def test_pair_by_internal_dates_and_discard_25th(tmp_path):
    from scripts.validation.gim.compare_legacy_modern import compare_pairs, read_modern
    a=tmp_path/'old'; b=tmp_path/'new'; a.mkdir(); b.mkdir()
    write_day(a,b,date(2022,1,1),bad_boundary=True)
    write_day(a,b,date(2022,1,2))
    old,new=select_pairs(a,b,date(2022,1,1),2)
    assert len(old)==len(new)==2
    assert read_modern(new[0])[0].shape[0]==24
    assert read_modern(new[1])[0][0]==np.datetime64('2022-01-02T00:00:00')
    compare_pairs(old,new,reference_days=15)  # No expensive science step.


def test_missing_day_fails(tmp_path):
    a=tmp_path/'old'; b=tmp_path/'new'; a.mkdir(); b.mkdir()
    write_day(a,b,date(2022,1,1))
    with pytest.raises(ValueError,match='Missing Legacy dates'):
        select_pairs(a,b,date(2022,1,1),2)


def test_duplicate_day_fails(tmp_path):
    a=tmp_path/'old'; b=tmp_path/'new'; a.mkdir(); b.mkdir()
    lp,mp=write_day(a,b,date(2022,1,1))
    (b/'duplicate.npz').write_bytes(mp.read_bytes())
    with pytest.raises(ValueError,match='Ambiguous Modern files'):
        select_pairs(a,b,date(2022,1,1),1)
