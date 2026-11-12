"""Import the HA-free modules (api, cycle) without loading Home Assistant."""
from pathlib import Path
import sys
import types

root = Path(__file__).parents[1] / "custom_components" / "hathway"
package = types.ModuleType("hathway_lib")
package.__path__ = [str(root)]
sys.modules["hathway_lib"] = package
