# JustCraft Player Handbook

Generated from `jc_information.json`.

- Game: Minetest Game
- Export timestamp: 2026-11-20T17:38:55Z
- Items: 19,457
- Entities: 250
- Crafting recipes: 21,440
- Cooking recipes with known outputs: 91
- Fuel records: 984

Open `index.html` for the searchable guide.

## Rankings and interpretation

- Weapon comparisons use exported damage groups. Where `full_punch_interval` exists, the guide calculates damage divided by that interval as a theoretical comparison only. It is not a measured in-game DPS value.
- Tool comparisons are separated by digging group and level. Lower exported dig time is faster. Durability uses are shown separately.
- Armor comparisons are separated by armor slot, damage group and source field. Values from different fields/systems are not combined into a universal armor score or converted to damage-reduction percentages.
- Missing values are displayed as unavailable rather than guessed.

## Recipes

- All exported recipe records are preserved in `recipes.json`.
- Shaped recipes use `recipe_width` and retain empty grid positions.
- Recipes with width zero are treated as shapeless.
- Group ingredients such as `group:wood` are described as any registered item belonging to that group.
- Alternate recipes remain separate records.
- Fuel records identify the fuel item in `items[0]`; their empty `output_item` is expected for this export format.
- 195 cooking records have no output identifier and cannot be presented as usable instructions.
- 0 cooking recipes with known outputs have no exported cooking time.

## Images

The HTML uses each item's `inventory_image` filename under the configured `--image-base` directory (default `images/`). The JSON export contains image names, not the image files themselves. Copy the corresponding Luanti textures to that directory or change the image base when generating. Missing images are hidden automatically.

## Regenerate

```bash
python3 generate_jc_information.py jc_information.json.gz
```

Optional arguments:

```bash
python3 generate_jc_information.py jc_information.json.gz --output public/justcraft --image-base ../textures
```

No third-party Python packages are required.
