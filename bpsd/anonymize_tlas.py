import json
import os

for filename in os.listdir("tla"):
    with open("tla/" + filename, "r") as f:
        data = json.load(f)

    data["file_path"] = ""
    data["media_path"] = ""

    with open("tla/" + filename, "w") as f:
        json.dump(data, f, indent=2)
