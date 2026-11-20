#!/usr/bin/env python3
"""Generate a player-friendly JustCraft reference from jc_information.json[.gz].

No third-party Python packages are required.
"""

import argparse
import gzip
import html
import json
import math
import re
from collections import defaultdict, Counter
from pathlib import Path


def esc(value):
    return html.escape(str(value), quote=True) if value is not None else ""


def number(value, digits=2):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return ""
    if not math.isfinite(value):
        return ""
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def clean_text(value):
    """Remove common Luanti translation/formatting markers, not the text."""
    if not isinstance(value, str):
        return ""
    value = value.replace("\x1bE", "")
    value = re.sub(r"\x1b\(T@[^)]*\)", "", value)
    value = re.sub(r"\x1b\([^)]*\)", "", value)
    value = re.sub(r"\x1b.", "", value)
    return value.strip()


def item_label(name, item_map=None):
    if not name:
        return "Player hand (built-in)"
    item = (item_map or {}).get(name)
    description = clean_text((item or {}).get("short_description") or (item or {}).get("description"))
    if description:
        return description
    short = str(name).split(":", 1)[-1].replace("_", " ").strip()
    return short.title() if short else str(name)


def parse_stack(value):
    """Return item name and count from a Luanti ItemStack string."""
    if not isinstance(value, str) or not value.strip():
        return "", None
    parts = value.strip().split()
    name = parts[0]
    count = None
    if len(parts) > 1:
        try:
            count = int(parts[1])
        except (TypeError, ValueError):
            pass
    return name, count


def load_json(path):
    with path.open("rb") as handle:
        magic = handle.read(2)
        handle.seek(0)
        if magic == b"\x1f\x8b" or path.suffix.lower() == ".gz":
            with gzip.open(handle, "rt", encoding="utf-8") as stream:
                return json.load(stream)
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)


def safe_dict(value):
    return value if isinstance(value, dict) else {}


def safe_list(value):
    return value if isinstance(value, list) else []


def armor_slot(item):
    groups = safe_dict(item.get("groups"))
    for key in ("armor_head", "armor_torso", "armor_legs", "armor_feet", "armor_shield"):
        if isinstance(groups.get(key), (int, float)) and groups[key] > 0:
            return key.replace("armor_", "")
    return "other"


def tool_families(item):
    caps = safe_dict(item.get("tool_capabilities"))
    groupcaps = safe_dict(caps.get("groupcaps"))
    families = []
    for group, label in (("cracky", "Pickaxe"), ("choppy", "Axe"), ("crumbly", "Shovel"), ("snappy", "Sword")):
        if group in groupcaps:
            families.append(label)
    if not families and groupcaps:
        families = ["Special tool"]
    return families


def is_weapon(item):
    caps = safe_dict(item.get("tool_capabilities"))
    damage = safe_dict(caps.get("damage_groups")) or safe_dict(item.get("damage_groups"))
    groups = safe_dict(item.get("groups"))
    name = (item.get("name") or "").lower()
    # A registered weapon group or explicit weapon-like name is sufficient.
    if groups.get("weapon"):
        return True
    if not damage:
        return False
    if any(word in name for word in ("sword", "whip", "spear", "dagger", "knife", "club", "bow", "crossbow")):
        return True
    # Snappy-only damage tools (e.g. swords) are weapons; digging tools remain tools.
    gc = safe_dict(caps.get("groupcaps"))
    return "snappy" in gc and not any(k in gc for k in ("cracky", "choppy", "crumbly"))


def is_tool(item):
    caps = safe_dict(item.get("tool_capabilities"))
    return bool(safe_dict(caps.get("groupcaps"))) or item.get("type") == "tool"


def recipe_sort_key(recipe):
    return (recipe.get("output_item") or "", recipe.get("method") or "", json.dumps(recipe, sort_keys=True, ensure_ascii=False))


def build_indexes(data):
    # The empty item name is Luanti's built-in hand definition; keep it as a useful baseline.
    items = [x for x in safe_list(data.get("items")) if isinstance(x, dict)]
    item_map = {x["name"]: x for x in items if x.get("name")}
    recipes = [x for x in safe_list(data.get("crafts")) if isinstance(x, dict)]
    by_output = defaultdict(list)
    by_group = defaultdict(list)
    for item in items:
        for group, value in safe_dict(item.get("groups")).items():
            if isinstance(value, (int, float)) and value > 0:
                by_group[group].append(item["name"])
    for recipe in recipes:
        method = recipe.get("method")
        output = recipe.get("output_item") or ""
        if output and method in ("normal", "cooking"):
            by_output[output].append(recipe)
    for output in by_output:
        by_output[output].sort(key=recipe_sort_key)
    return items, item_map, recipes, by_output, by_group


def ranking_rows(items):
    weapons, tools, armor = [], [], []
    for item in items:
        caps = safe_dict(item.get("tool_capabilities"))
        damage = safe_dict(caps.get("damage_groups")) or safe_dict(item.get("damage_groups"))
        groups = safe_dict(item.get("groups"))
        gc = safe_dict(caps.get("groupcaps"))
        if is_weapon(item):
            interval = caps.get("full_punch_interval")
            for dtype, value in damage.items():
                if isinstance(value, (int, float)):
                    dps = value / interval if isinstance(interval, (int, float)) and interval > 0 else None
                    weapons.append({"item": item, "damage_type": dtype, "damage": value, "interval": interval, "estimate": dps})
        if is_tool(item):
            for group, info in gc.items():
                info = safe_dict(info)
                times = safe_list(info.get("times"))
                for level, seconds in enumerate(times, 1):
                    if isinstance(seconds, (int, float)) and seconds > 0:
                        tools.append({"item": item, "group": group, "level": level, "seconds": seconds,
                                      "uses": info.get("uses"), "maxlevel": info.get("maxlevel")})
        if item.get("category") == "armor" or any(k.startswith("armor_") and isinstance(v, (int, float)) and v > 0 for k, v in groups.items()):
            slot = armor_slot(item)
            ag = safe_dict(item.get("armor_groups"))
            if ag:
                for dtype, value in ag.items():
                    if isinstance(value, (int, float)):
                        armor.append({"item": item, "slot": slot, "type": dtype, "value": value, "source": "armor_groups"})
            # Preserve alternate systems' exported slot values as a separate comparison.
            slot_key = "armor_" + slot
            if slot != "other" and isinstance(groups.get(slot_key), (int, float)) and groups[slot_key] > 1:
                armor.append({"item": item, "slot": slot, "type": "slot value", "value": groups[slot_key], "source": "groups." + slot_key})
    return weapons, tools, armor


def format_ingredient(value, item_map, by_group, max_group_members=3):
    if value is None or value == "":
        return ""
    if not isinstance(value, str):
        return str(value)
    if value.startswith("group:"):
        group = value[6:]
        members = by_group.get(group, [])
        sample = ", ".join(item_label(n, item_map) for n in members[:max_group_members])
        more = f" (+{len(members) - max_group_members} more)" if len(members) > max_group_members else ""
        suffix = f" — examples: {sample}{more}" if sample else " — no matching registered items found"
        return f"Any item in group '{group}'{suffix}"
    name, count = parse_stack(value)
    label = item_label(name, item_map)
    return f"{count} × {label}" if count and count > 1 else label


def recipe_description(recipe, item_map, by_group):
    method = recipe.get("method")
    ingredients = [x for x in safe_list(recipe.get("items")) if x]
    if method == "normal":
        width = recipe.get("recipe_width")
        if isinstance(width, (int, float)) and width > 0:
            return "Arrange the ingredients in the crafting grid as shown. Empty cells must remain empty."
        return "Place the listed ingredients in the crafting grid. Their positions do not matter (shapeless recipe)."
    if method == "cooking":
        source = recipe.get("cook_input") or (ingredients[0] if ingredients else "")
        duration = recipe.get("cook_time_seconds")
        if source and isinstance(duration, (int, float)):
            return f"Cook {item_label(source, item_map)} in a furnace for {number(duration)} seconds."
        if source:
            return f"A cooking recipe is registered for {item_label(source, item_map)}, but the export has no verified cooking time."
        return "Cooking recipe details are incomplete in the export."
    return ""


def render_recipe(recipe, item_map, by_group, index, dependency_html=""):
    method = recipe.get("method")
    output = recipe.get("output_item") or ""
    output_stack = recipe.get("output") or output
    _, output_count = parse_stack(output_stack)
    ingredients = safe_list(recipe.get("items"))
    valid_ingredients = [x for x in ingredients if x]
    title = item_label(output, item_map) if output else "Fuel source"
    if method == "fuel":
        source = valid_ingredients[0] if valid_ingredients else ""
        burn = recipe.get("burn_time_seconds")
        return (f'<article class="recipe-card searchable" data-search="{esc((source or "") + " " + item_label(source, item_map))}">'
                f'<div class="recipe-head"><strong>Fuel: {esc(item_label(source, item_map))}</strong>'
                f'<span class="tag">Fuel</span></div><p>Burns for <b>{esc(number(burn) or "Not available")}</b> seconds per item.</p>'
                f'<small class="muted">{esc(source)}</small></article>')

    description = recipe_description(recipe, item_map, by_group)
    method_label = "Crafting" if method == "normal" else "Cooking"
    html_parts = [f'<article class="recipe-card searchable" data-search="{esc(output + " " + title + " " + " ".join(str(x) for x in valid_ingredients))}">']
    html_parts.append(f'<div class="recipe-head"><strong>{esc(title)}</strong><span class="tag">{esc(method_label)}</span></div>')
    if output_count and output_count > 1:
        html_parts.append(f'<p class="muted">Produces {output_count} items.</p>')
    html_parts.append(f'<p>{esc(description)}</p>')
    if method == "normal":
        width = recipe.get("recipe_width")
        if isinstance(width, (int, float)) and width > 0:
            width = max(1, min(9, int(width)))
            cells = []
            for value in ingredients:
                if value:
                    cells.append(f'<div class="craft-cell" title="{esc(value)}">{esc(format_ingredient(value, item_map, by_group))}</div>')
                else:
                    cells.append('<div class="craft-cell empty">&nbsp;</div>')
            while len(cells) % width:
                cells.append('<div class="craft-cell empty">&nbsp;</div>')
            html_parts.append(f'<div class="craft-grid" style="--grid-width:{width}">{"".join(cells)}</div>')
        else:
            html_parts.append('<div class="ingredient-list">' + ''.join(f'<span class="ingredient">{esc(format_ingredient(x, item_map, by_group))}</span>' for x in valid_ingredients) + '</div>')
    elif method == "cooking":
        source = recipe.get("cook_input") or (valid_ingredients[0] if valid_ingredients else "")
        html_parts.append(f'<p><b>Input:</b> {esc(format_ingredient(source, item_map, by_group))}</p>')
        t = recipe.get("cook_time_seconds")
        html_parts.append(f'<p><b>Cooking time:</b> {esc(number(t) + " seconds" if isinstance(t, (int, float)) else "Not available in export")}</p>')
    if dependency_html:
        html_parts.append(dependency_html)
    html_parts.append(f'<small class="muted">Recipe record #{index + 1} · {esc(output)}</small></article>')
    return ''.join(html_parts)


def dependency_tree(item_name, by_output, item_map, by_group, seen=None, depth=0, budget=None):
    """Show one possible dependency path; cycles and large branches are bounded."""
    if seen is None:
        seen = set()
    if budget is None:
        budget = [30]
    if depth >= 5 or budget[0] <= 0:
        return ""
    if item_name in seen:
        return f'<li>{esc(item_label(item_name, item_map))} <em>(dependency cycle)</em></li>'
    recipes = by_output.get(item_name, [])
    recipe = next((r for r in recipes if r.get("method") == "normal"), None)
    if not recipe:
        return ""
    seen = set(seen)
    seen.add(item_name)
    children = []
    for value in safe_list(recipe.get("items")):
        if not value:
            continue
        budget[0] -= 1
        if budget[0] < 0:
            break
        if isinstance(value, str) and value.startswith("group:"):
            children.append(f'<li>{esc(format_ingredient(value, item_map, by_group))}</li>')
        else:
            ingredient, count = parse_stack(value)
            nested = dependency_tree(ingredient, by_output, item_map, by_group, seen, depth + 1, budget)
            label = item_label(ingredient, item_map)
            qty = f" ({count} required)" if count and count > 1 else ""
            children.append(f'<li>{esc(label + qty)}{("<ul>" + nested + "</ul>") if nested else ""}</li>')
    return ''.join(children)


def item_details(item, item_map, by_output, by_group, image_base):
    name = item.get("name") or ""
    desc = clean_text(item.get("short_description") or item.get("description"))
    display_name = desc or item_label(name, item_map)
    if not desc:
        desc = "No description was provided by the registered item definition."
    caps = safe_dict(item.get("tool_capabilities"))
    damage = safe_dict(caps.get("damage_groups")) or safe_dict(item.get("damage_groups"))
    groups = safe_dict(item.get("groups"))
    details = []
    if damage:
        details.append("Damage: " + ", ".join(f"{k} {number(v)}" for k, v in sorted(damage.items())))
    if caps.get("full_punch_interval") is not None:
        details.append(f"Full-punch interval: {number(caps.get('full_punch_interval'))} s")
    if caps.get("punch_attack_uses") is not None:
        details.append(f"Punch durability: {number(caps.get('punch_attack_uses'))} uses")
    gc = safe_dict(caps.get("groupcaps"))
    for group, info in gc.items():
        info = safe_dict(info)
        uses = info.get("uses")
        maxlevel = info.get("maxlevel")
        details.append(f"Digging group {group}: max level {number(maxlevel) or 'not specified'}, uses {number(uses) or 'not specified'}")
    ag = safe_dict(item.get("armor_groups"))
    if ag:
        details.append("Armor protection groups: " + ", ".join(f"{k} {number(v)}" for k, v in sorted(ag.items())))
    slot_values = [(k, v) for k, v in groups.items() if k.startswith("armor_") and isinstance(v, (int, float)) and v]
    if slot_values:
        details.append("Armor-related groups: " + ", ".join(f"{k} {number(v)}" for k, v in sorted(slot_values)))
    if item.get("stack_max") is not None:
        details.append(f"Maximum stack: {number(item.get('stack_max'))}")
    relevant_groups = [(k, v) for k, v in groups.items() if not k.startswith("not_in_creative_inventory")]
    group_text = ", ".join(f"{k}={number(v)}" for k, v in sorted(relevant_groups)[:18])
    image = item.get("inventory_image") or ""
    image_url = (image_base.rstrip("/") + "/" + image.lstrip("/")) if image and image_base else ""
    recipes = by_output.get(name, [])
    recipe_link = f'<a href="#recipes" class="recipe-count">{len(recipes)} known crafting/cooking recipe(s)</a>' if recipes else '<span class="muted">No crafting or cooking recipe found in this export.</span>'
    dependency = dependency_tree(name, by_output, item_map, by_group, budget=[12]) if recipes else ""
    dependency_html = (
        '<details><summary>One possible ingredient chain</summary><ul>' + dependency +
        '</ul><small>Uses one available normal recipe at each step. Other recipes remain available in the recipe guide.</small></details>'
        if dependency else ""
    )
    img = f'<img loading="lazy" src="{esc(image_url)}" alt="" onerror="this.hidden=true">' if image_url else '<span class="no-image">No image</span>'
    return (f'<tr class="searchable" data-search="{esc(name + " " + desc + " " + item.get("mod", "") + " " + group_text)}">'
            f'<td class="item-name">{img}<span><b>{esc(display_name)}</b><small>{esc(name or '(empty item name)')}</small></span></td>'
            f'<td>{esc(item.get("mod") or "unknown")}</td><td>{esc(item.get("category") or "item")}</td>'
            f'<td>{esc("; ".join(details))}<details><summary>Groups</summary>{esc(group_text or "No groups")}</details><div>{recipe_link}</div>{dependency_html}</td></tr>')


def render_ranking_tables(weapons, tools, armor, item_map):
    out = []
    out.append('<section id="weapons"><h2>Weapon comparisons</h2><p class="intro">Rankings use the exported damage-group values. The damage-per-interval figure is a theoretical comparison (damage value ÷ full-punch interval), not a promise of in-game DPS. Different damage types are ranked separately.</p>')
    for dtype in sorted({r["damage_type"] for r in weapons}):
        rows = [r for r in weapons if r["damage_type"] == dtype]
        rows.sort(key=lambda r: (r["damage"], r["estimate"] if r["estimate"] is not None else -1, r["item"].get("name", "")))
        out.append(f'<h3>{esc(dtype.title())} damage · weakest to strongest</h3><table><thead><tr><th>Rank</th><th>Weapon</th><th>Damage value</th><th>Full-punch interval</th><th>Comparison estimate</th></tr></thead><tbody>')
        last = None; rank = 0
        for i, r in enumerate(rows, 1):
            score = (r["damage"], r["estimate"])
            if score != last: rank = i; last = score
            out.append(f'<tr class="searchable" data-search="{esc(r["item"].get("name", "") + " " + item_label(r["item"].get("name"), item_map))}"><td>{rank}</td><td>{esc(item_label(r["item"].get("name"), item_map))}<small>{esc(r["item"].get("name"))}</small></td><td>{esc(number(r["damage"]))}</td><td>{esc(number(r["interval"]) + " s" if r["interval"] else "Not exported")}</td><td>{esc(number(r["estimate"]) if r["estimate"] is not None else "Not calculable")}</td></tr>')
        out.append('</tbody></table>')
    out.append('</section>')

    out.append('<section id="tools"><h2>Tool comparisons</h2><p class="intro">Lower digging time is faster. Values are compared only within the same digging group and level. Durability is shown as exported uses; it is not converted into an overall score.</p>')
    groups = sorted({(r["group"], r["level"]) for r in tools})
    for group, level in groups:
        rows = [r for r in tools if r["group"] == group and r["level"] == level]
        rows.sort(key=lambda r: (r["seconds"], r["item"].get("name", "")))
        out.append(f'<h3>{esc(group)} · level {level} · fastest to slowest</h3><table><thead><tr><th>Rank</th><th>Tool</th><th>Dig time</th><th>Durability uses</th><th>Maximum level</th></tr></thead><tbody>')
        last = None; rank = 0
        for i, r in enumerate(rows, 1):
            if r["seconds"] != last: rank = i; last = r["seconds"]
            uses = number(r["uses"]) if r["uses"] is not None else "Not exported"
            out.append(f'<tr class="searchable" data-search="{esc(r["item"].get("name", "") + " " + item_label(r["item"].get("name"), item_map))}"><td>{rank}</td><td>{esc(item_label(r["item"].get("name"), item_map))}<small>{esc(r["item"].get("name"))}</small></td><td>{esc(number(r["seconds"]))} s</td><td>{esc(uses)}</td><td>{esc(number(r["maxlevel"]) or "Not exported")}</td></tr>')
        out.append('</tbody></table>')
    out.append('</section>')

    out.append('<section id="armor"><h2>Armor comparisons</h2><p class="intro">Armor values are kept in separate comparisons by exported field and damage type. Values from different armor systems or fields are not mixed, and these numbers are not presented as damage-reduction percentages.</p>')
    keys = sorted({(r["slot"], r["type"], r["source"]) for r in armor})
    for slot, dtype, source in keys:
        rows = [r for r in armor if (r["slot"], r["type"], r["source"]) == (slot, dtype, source)]
        rows.sort(key=lambda r: (r["value"], r["item"].get("name", "")))
        out.append(f'<h3>{esc(slot.title())} · {esc(dtype)} · {esc(source)} · lowest to highest</h3><table><thead><tr><th>Rank</th><th>Armor</th><th>Exported value</th><th>Mod</th></tr></thead><tbody>')
        last = None; rank = 0
        for i, r in enumerate(rows, 1):
            if r["value"] != last: rank = i; last = r["value"]
            out.append(f'<tr class="searchable" data-search="{esc(r["item"].get("name", "") + " " + item_label(r["item"].get("name"), item_map))}"><td>{rank}</td><td>{esc(item_label(r["item"].get("name"), item_map))}<small>{esc(r["item"].get("name"))}</small></td><td>{esc(number(r["value"]))}</td><td>{esc(r["item"].get("mod") or "unknown")}</td></tr>')
        out.append('</tbody></table>')
    out.append('</section>')
    return ''.join(out)


def main():
    parser = argparse.ArgumentParser(description="Generate the JustCraft player reference website.")
    parser.add_argument("input", nargs="?", default="jc_information.json", help="Input JSON or .json.gz export")
    parser.add_argument("-o", "--output", default="jc_information_docs", help="Output directory")
    parser.add_argument("--image-base", default="images", help="Relative URL/path prefix for inventory images; use empty string to disable")
    args = parser.parse_args()
    source = Path(args.input)
    outdir = Path(args.output)
    data = load_json(source)
    items, item_map, crafts, by_output, by_group = build_indexes(data)
    entities = [x for x in safe_list(data.get("entities")) if isinstance(x, dict) and x.get("name")]
    weapons, tools, armor = ranking_rows(items)

    categories = defaultdict(list)
    for item in items:
        cat = item.get("category") or "item"
        if cat == "weapon_or_tool" or not item.get("name"):
            # Hybrid tools and Luanti's built-in hand are grouped with equipment.
            cat = "tools and weapons"
        elif cat == "item":
            cat = "other items"
        categories[cat].append(item)

    outdir.mkdir(parents=True, exist_ok=True)
    image_base = args.image_base
    item_rows = []
    for cat in sorted(categories):
        item_rows.append(f'<h3>{esc(cat.replace("_", " ").title())} ({len(categories[cat])})</h3><table><thead><tr><th>Item</th><th>Mod</th><th>Type</th><th>Capabilities and information</th></tr></thead><tbody>')
        for item in sorted(categories[cat], key=lambda x: x.get("name", "")):
            item_rows.append(item_details(item, item_map, by_output, by_group, image_base))
        item_rows.append('</tbody></table>')

    recipe_sections = []
    valid_normal = [r for r in crafts if r.get("method") == "normal" and r.get("output_item")]
    valid_cooking = [r for r in crafts if r.get("method") == "cooking" and r.get("output_item")]
    fuels = [r for r in crafts if r.get("method") == "fuel" and safe_list(r.get("items"))]
    invalid_cooking = [r for r in crafts if r.get("method") == "cooking" and not r.get("output_item")]
    all_valid = sorted(valid_normal + valid_cooking + fuels, key=recipe_sort_key)
    for i, recipe in enumerate(all_valid):
        # Keep the main handbook compact. Direct dependencies are included in recipes.json;
        # recursive dependency expansion can be added as an on-demand browser view.
        recipe_sections.append(render_recipe(recipe, item_map, by_group, i))

    entity_rows = []
    for entity in sorted(entities, key=lambda x: x.get("name", "")):
        props = safe_dict(entity.get("initial_properties"))
        hp_min = entity.get("hp_min")
        hp_max = entity.get("hp_max") if entity.get("hp_max") is not None else props.get("hp_max")
        hp = (f"{number(hp_min)}–{number(hp_max)}" if hp_min is not None and hp_max is not None else number(hp_max) or number(hp_min) or "Not exported")
        drops = safe_list(entity.get("drops"))
        drop_text = ', '.join(f"{d.get('name', 'unknown')} ({number(d.get('min')) or '?'}–{number(d.get('max')) or '?'}, chance {number(d.get('chance')) or '?'})" for d in drops if isinstance(d, dict)) or "No drop data exported"
        desc = clean_text(entity.get("description")) or item_label(entity.get("name"))
        ag = safe_dict(entity.get("armor_groups")) or safe_dict(props.get("armor_groups"))
        armor_text = ', '.join(f"{k}={number(v)}" for k, v in sorted(ag.items())) or "Not exported"
        physical = props.get("physical")
        entity_rows.append(f'<tr class="searchable" data-search="{esc(entity.get("name", "") + " " + desc + " " + entity.get("mod", ""))}"><td><b>{esc(desc)}</b><small>{esc(entity.get("name"))}</small></td><td>{esc(entity.get("mod") or "unknown")}</td><td>{esc(hp)}</td><td>{esc(armor_text)}</td><td>{esc(drop_text)}</td><td>{esc("Yes" if physical else "No" if physical is False else "Not exported")}</td></tr>')

    game = safe_dict(data.get("game"))
    title = clean_text(game.get("title")) or "JustCraft"
    generated = data.get("generated_at") or "Not recorded"
    total_normal = len([r for r in crafts if r.get("method") == "normal"])
    total_fuel = len([r for r in crafts if r.get("method") == "fuel"])
    cooking_times = [r.get("cook_time_seconds") for r in valid_cooking if isinstance(r.get("cook_time_seconds"), (int, float))]
    missing_cook = sum(not isinstance(r.get("cook_time_seconds"), (int, float)) for r in valid_cooking)
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="Player reference for items, weapons, tools, armor, crafting, cooking, fuel and creatures in JustCraft."><title>JustCraft Player Handbook</title>
<link rel="stylesheet" href="style.css"></head><body><header><h1>JustCraft Player Handbook</h1><p>Items, equipment, crafting, cooking, fuel and creatures from the live server export.</p></header><main class="wrap"><div class="stats"><div class="stat"><b>{len(items):,}</b>Items</div><div class="stat"><b>{len(weapons):,}</b>Weapon damage entries</div><div class="stat"><b>{len(tools):,}</b>Tool capability entries</div><div class="stat"><b>{len(armor):,}</b>Armor value entries</div><div class="stat"><b>{len(valid_normal):,}</b>Crafting recipes</div><div class="stat"><b>{len(entities):,}</b>Entities</div></div><p class="muted">Game: {esc(title)} · Exported: {esc(generated)} · Schema: {esc(data.get('schema_version'))}</p><div class="toolbar"><input id="search" type="search" placeholder="Search items, mods, ingredients, recipes or creatures…"><nav><a href="#items">Items</a><a href="#weapons">Weapons</a><a href="#tools">Tools</a><a href="#armor">Armor</a><a href="#recipes">Recipes</a><a href="#fuel">Fuel</a><a href="#entities">Creatures & entities</a></nav></div>
<section id="items"><h2>Item catalogue</h2><p class="intro">Descriptions and properties come from registered item definitions. Missing values are left unspecified. Images use the inventory_image filename from the export and the configured image path.</p>{''.join(item_rows)}</section>
{render_ranking_tables(weapons, tools, armor, item_map)}
<section id="recipes"><h2>Crafting and cooking guide</h2><p class="intro">Every usable crafting and cooking record is retained, including alternate recipes. Shaped recipes preserve empty grid cells; shapeless recipes list ingredients without assigning positions.</p><div class="notice">Cooking recipes with missing output identifiers are omitted from player instructions because the export cannot identify what they produce. There are {len(invalid_cooking)} such incomplete records. Among the {len(valid_cooking)} cooking recipes with known outputs, {missing_cook} have no exported cooking time.</div><div class="recipe-grid">{''.join(x for x in recipe_sections if 'Fuel:' not in x)}</div></section>
<section id="fuel"><h2>Fuel guide</h2><p class="intro">Fuel burn times are the values exported by Luanti. They describe the burn duration of one fuel item.</p><div class="recipe-grid">{''.join(render_recipe(r, item_map, by_group, i) for i, r in enumerate(fuels))}</div></section>
<section id="entities"><h2>Creatures and registered entities</h2><p class="intro">Some registered entities are technical objects, projectiles or effects rather than creatures. Health, armor and drops are shown only when the export contains those values.</p><table><thead><tr><th>Entity</th><th>Mod</th><th>Health</th><th>Armor groups</th><th>Drops</th><th>Physical</th></tr></thead><tbody>{''.join(entity_rows)}</tbody></table></section>
</main><footer>Generated from {esc(source.name)} · No external JavaScript or CSS libraries are used. Search filters visible catalogue, comparison and entity rows/cards.</footer><script>const search=document.getElementById('search');search.addEventListener('input',()=>{{const q=search.value.trim().toLowerCase();document.querySelectorAll('.searchable').forEach(el=>{{el.hidden=q!==''&&!((el.dataset.search||el.textContent).toLowerCase().includes(q));}});}});</script></body></html>'''

    (outdir / "index.html").write_text(page, encoding="utf-8")

    # Cleaned/enriched JSON files retain original source records and add readable labels/analysis.
    cleaned_items = []
    for item in items:
        entry = dict(item)
        entry["display_name"] = item_label(item.get("name"), item_map)
        entry["clean_description"] = clean_text(item.get("short_description") or item.get("description"))
        entry["weapon"] = is_weapon(item)
        entry["tool"] = is_tool(item)
        entry["armor_slot"] = armor_slot(item) if item.get("category") == "armor" else None
        cleaned_items.append(entry)
    (outdir / "items.json").write_text(json.dumps(cleaned_items, indent=2, ensure_ascii=False), encoding="utf-8")

    cleaned_recipes = []
    for i, recipe in enumerate(crafts):
        entry = dict(recipe)
        entry["record_index"] = i
        entry["display_output"] = item_label(recipe.get("output_item"), item_map) if recipe.get("output_item") else None
        entry["ingredient_descriptions"] = [format_ingredient(x, item_map, by_group) for x in safe_list(recipe.get("items")) if x]
        entry["dependency_outputs"] = [x for x in safe_list(recipe.get("items")) if isinstance(x, str) and x in by_output]
        cleaned_recipes.append(entry)
    (outdir / "recipes.json").write_text(json.dumps(cleaned_recipes, indent=2, ensure_ascii=False), encoding="utf-8")

    (outdir / "entities.json").write_text(json.dumps(entities, indent=2, ensure_ascii=False), encoding="utf-8")

    # Human-readable README: concise overview and data limitations.
    readme = f'''# JustCraft Player Handbook\n\nGenerated from `{source.name}`.\n\n- Game: {title}\n- Export timestamp: {generated}\n- Items: {len(items):,}\n- Entities: {len(entities):,}\n- Crafting recipes: {len(valid_normal):,}\n- Cooking recipes with known outputs: {len(valid_cooking):,}\n- Fuel records: {len(fuels):,}\n\nOpen `index.html` for the searchable guide.\n\n## Rankings and interpretation\n\n- Weapon comparisons use exported damage groups. Where `full_punch_interval` exists, the guide calculates damage divided by that interval as a theoretical comparison only. It is not a measured in-game DPS value.\n- Tool comparisons are separated by digging group and level. Lower exported dig time is faster. Durability uses are shown separately.\n- Armor comparisons are separated by armor slot, damage group and source field. Values from different fields/systems are not combined into a universal armor score or converted to damage-reduction percentages.\n- Missing values are displayed as unavailable rather than guessed.\n\n## Recipes\n\n- All exported recipe records are preserved in `recipes.json`.\n- Shaped recipes use `recipe_width` and retain empty grid positions.\n- Recipes with width zero are treated as shapeless.\n- Group ingredients such as `group:wood` are described as any registered item belonging to that group.\n- Alternate recipes remain separate records.\n- Fuel records identify the fuel item in `items[0]`; their empty `output_item` is expected for this export format.\n- {len(invalid_cooking)} cooking records have no output identifier and cannot be presented as usable instructions.\n- {missing_cook} cooking recipes with known outputs have no exported cooking time.\n\n## Images\n\nThe HTML uses each item's `inventory_image` filename under the configured `--image-base` directory (default `images/`). The JSON export contains image names, not the image files themselves. Copy the corresponding Luanti textures to that directory or change the image base when generating. Missing images are hidden automatically.\n\n## Regenerate\n\n```bash\npython3 generate_jc_information.py jc_information.json.gz\n```\n\nOptional arguments:\n\n```bash\npython3 generate_jc_information.py jc_information.json.gz --output public/justcraft --image-base ../textures\n```\n\nNo third-party Python packages are required.\n'''
    (outdir / "README.md").write_text(readme, encoding="utf-8")

    print(f"Generated documentation in: {outdir.resolve()}")
    print(f"Items: {len(items):,}; entities: {len(entities):,}; recipes: {len(crafts):,}")
    print(f"Usable crafting: {len(valid_normal):,}; cooking: {len(valid_cooking):,}; fuel: {len(fuels):,}")
    print(f"Incomplete cooking records (no output): {len(invalid_cooking):,}; missing cooking times: {missing_cook:,}")


if __name__ == "__main__":
    main()
