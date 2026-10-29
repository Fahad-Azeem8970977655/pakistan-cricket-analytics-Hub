# Cleanup log
Removed from the deploy copy (all still in pakistan_cricket_dashboard_FULL_BACKUP.zip):
- data_backup/        old copy of data/, not read by any code
- output_v3/          build-script intermediate, duplicate of data/
- incoming/           raw inputs, only used by scripts/add_opposition_data.py
- cricsheet_data/     raw Cricsheet zips (61 MB), only needed to rebuild the dataset
- eras/source_archive old coach spreadsheets (superseded by pakistan_cricket_coaches_corrected.xlsx)
- tests/              empty folder
- __pycache__/        compiled cache
- .streamlit/secrets.toml  contained a live API key; replaced by secrets.toml.example
To rebuild the dataset from raw sources, restore incoming/, cricsheet_data/ and output_v3/ from the backup.
