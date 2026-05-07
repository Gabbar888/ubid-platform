# Nominatim data directory

Drop the Karnataka OpenStreetMap extract into this folder to enable
self-hosted geocoding.

## Step-by-step

### 1. Download the OSM extract

Pick **one** of these from Geofabrik (free, no signup):

| Extract | Size | Coverage | Best for |
|---|---|---|---|
| **`karnataka-latest.osm.pbf`** | ~250 MB | Karnataka only | ✅ Recommended for this platform |
| `india-latest.osm.pbf` | ~5 GB | Whole India | If users span multiple states |
| `southern-zone-latest.osm.pbf` | ~1.2 GB | KA + TN + KL + AP + TS + Pondy | If you also process neighbouring states |

Download links:
- Karnataka: <https://download.geofabrik.de/asia/india/karnataka.html>
  → click **"karnataka-latest.osm.pbf"**
- India:    <https://download.geofabrik.de/asia/india.html>

### 2. Place the file here

Copy it directly into this folder:

```
ubid_platform/
├── nominatim_data/
│   └── karnataka-latest.osm.pbf      ← drop the file here
└── ...
```

Filename **must** be exactly `karnataka-latest.osm.pbf` (or update the
`PBF_PATH` env var in `docker-compose.yml`).

### 3. Enable the Nominatim service

Open `../docker-compose.yml`. Find the block beginning with
`# nominatim:` (around line 195). **Uncomment** every line in that block
and the `# nominatim_db:` line at the bottom under `volumes:`.

### 4. Add the URL to `.env`

Append this line to `../ .env`:

```bash
NOMINATIM_URL=http://nominatim:8080
```

### 5. Start the service

```powershell
cd ..
docker compose up -d nominatim
```

**First-time import takes ~10-30 minutes** — Nominatim is building a
PostgreSQL database from the .pbf file. Check progress with:

```powershell
docker logs -f ubid_platform-nominatim-1
```

You'll know it's ready when the logs settle into "ready for connections"
or similar.

### 6. Restart the API to pick up the new env var

```powershell
docker compose up -d --force-recreate ubid-api
```

### 7. Re-run the geocoding backfill

```powershell
docker cp scripts/backfill_geocoding.py ubid_platform-ubid-api-1:/app/scripts/
docker exec ubid_platform-ubid-api-1 python /app/scripts/backfill_geocoding.py
```

This time Nominatim will resolve any address that wasn't matched by the
locality dictionary. Expect ~85-95% coverage including building-level
precision (~5 m) instead of locality centroids.

### 8. Retrain the model and re-score pairs

In the Streamlit UI:

- **Admin → Retrain → Trigger retrain** (LightGBM picks up the new
  `addr_geo_distance_km` signal)
- **Admin → Re-score pairs → Smart → Re-score now**

### 9. Re-evaluate

```powershell
docker exec ubid_platform-ubid-api-1 python /app/scripts/evaluate.py
```

Expected lift: pairwise recall **+5-8 points**, B3 F1 **+2-3 points**.

---

## Troubleshooting

**"PBF file not found" in Nominatim logs**
The container looks at `/nominatim/data/<PBF_PATH>`. Check the file is at
the right host path (`nominatim_data/karnataka-latest.osm.pbf`) and that
the volume mount in `docker-compose.yml` reads `./nominatim_data:/nominatim/data`.

**Nominatim is using ~3 GB RAM**
Normal during the first import. After import finishes, idle memory drops
to ~512 MB. Increase Docker Desktop's memory allocation if it OOM-kills.

**Import is taking forever**
Karnataka extract import on a typical laptop: ~15 min. India extract:
30-60 min. If your container died mid-import, delete the
`nominatim_db` volume and retry:

```powershell
docker compose down nominatim
docker volume rm ubid_platform_nominatim_db
docker compose up -d nominatim
```

**Geocoding is slow at query time**
First few queries warm the index. After that, ~5 ms per query is typical.

---

## Why is this folder otherwise empty?

The `.osm.pbf` file is too big to commit to git. Each operator downloads
it themselves. The folder exists in the repo so the volume mount in
`docker-compose.yml` doesn't fail with "no such file or directory".
