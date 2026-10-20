from datetime import date
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts.validation.gim.run_integrated_validation import legacy_base, commands

def test_base_folder():
    assert legacy_base(Path('I:/IRSL/GIMTEC2022'), date(2022,1,1),16) == Path('I:/IRSL/GIMTEC')

def test_bad_year():
    with pytest.raises(ValueError, match='must end'):
        legacy_base(Path('GIMTEC2021'), date(2022,1,1),16)

def test_cross_year_rejected():
    with pytest.raises(ValueError, match='Cross-year'):
        legacy_base(Path('GIMTEC2022'), date(2022,12,25),16)

def test_commands_use_actual_year_folder():
    args = SimpleNamespace(legacy_dir=Path('GIMTEC2022'),modern_dir=Path('processed'),start=date(2022,1,1),days=16,reference_days=15,window_steps=24,latitude=30.,longitude=70.,k=3.)
    jobs=commands(args,Path('.'))
    assert [x[0] for x in jobs]==['D','A','B+C']
    for _, cmd in jobs:
        assert cmd[cmd.index('--legacy-dir')+1]=='GIMTEC2022'
