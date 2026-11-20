# jc_information

A server-side Luanti mod that exports registered game information for the JustCraft player reference website.

## Load order

The mod uses `core.register_on_mods_loaded()`. This callback runs after all mods have completed registration, so `jc_information` does not need to be forced to the end of the mod load order and does not need dependencies on every installed mod.

## Output

On startup, the mod writes `jc_information.json` in the active world's directory. The JSON currently includes:

- Registered items and their descriptions, groups, images, and tool capabilities
- Registered entities and available health, damage, armor, and drop properties
- Registered crafting recipes, including cooking times and fuel burn times where the engine exposes them
- Export timestamp and game information

The server operator can regenerate the file at any time with:

`/jc_information_export`

The command requires the `server` privilege.

## Current limitations

This is the first exporter pass (version 0.1.2). Armor systems and some weapon mods store effective values in custom fields or calculate them at runtime. Those need mod-specific adapters before the guide can claim complete protection, durability, or damage rankings. Recipe output is exported as registered; the separate documentation generator will build recipe relationships and explain them in player-friendly language.

On older Luanti versions, cooking and fuel times are queried through `core.get_craft_result()` when they are not included in recipe metadata. Fuel recipes are also discovered this way when `get_all_craft_recipes("")` is not supported. The exporter intentionally copies only JSON-safe fields and avoids serializing functions or entire mod definitions.
