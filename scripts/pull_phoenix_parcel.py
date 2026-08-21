"""Live pull 1 satellite + 1 streetview for Phoenix center (gated). Also fetch 2 extra dates for heat-wave demo."""
from dotenv import load_dotenv
load_dotenv()
from fortyguard import FortyGuardClient
import pathlib, json

c = FortyGuardClient()
# Phoenix center
lat, lon = 33.4484, -112.0740
print("Pulling satellite for Phoenix center...")
# Use a small polygon around center? satellite_segmentation expects polygon? Check client signature
import inspect
print(inspect.signature(c.satellite_segmentation))
try:
    sat = c.satellite_segmentation(polygon_geojson={"type":"Polygon","coordinates":[[[lon-0.01,lat-0.01],[lon+0.01,lat-0.01],[lon+0.01,lat+0.01],[lon-0.01,lat+0.01],[lon-0.01,lat-0.01]]]}, verbose=False)
    print("sat keys", list(sat.keys())[:5] if isinstance(sat, dict) else type(sat))
    pathlib.Path("data/satellite/satellite_parcel_phoenix_2024-07-15.json").write_text(json.dumps(sat, indent=2))
    print("saved satellite")
except Exception as e:
    print("sat error", e)

print(inspect.signature(c.street_view_segmentation))
try:
    sv = c.street_view_segmentation(latitude=lat, longitude=lon, verbose=False)
    print("sv keys", list(sv.keys())[:5] if isinstance(sv, dict) else type(sv))
    pathlib.Path("data/street_view/streetview_parcel_phoenix.json").write_text(json.dumps(sv, indent=2))
    print("saved streetview")
except Exception as e:
    print("sv error", e)

# 3-date env for heat-wave (2024-07-13,14)
for date in ["2024-07-13","2024-07-14"]:
    try:
        from calorai.data_source import LiveFortyGuardSource
        src = LiveFortyGuardSource()
        env = src.get_environmental_parameters("phoenix", date)
        print(f"env {date} ok {len(env.apparent_c)} hours")
    except Exception as e:
        print(f"env {date} error", e)
