local modname = core.get_current_modname()
local modpath = core.get_modpath(modname)
local worldpath = core.get_worldpath()
local output_file = worldpath .. "/jc_information.json"

local function log(level, message)
  core.log(level, "[" .. modname .. "] " .. message)
end

local function copy_value(value, seen, depth)
  local value_type = type(value)

  if value_type == "nil" or value_type == "boolean" or value_type == "number" or value_type == "string" then
    return value
  end

  if value_type ~= "table" or depth > 12 then
    return nil
  end

  if seen[value] then
    return nil
  end

  seen[value] = true

  local result = {}
  for key, child in pairs(value) do
    local key_type = type(key)
    if key_type == "string" or key_type == "number" then
      local copied = copy_value(child, seen, depth + 1)
      if copied ~= nil then
        result[key] = copied
      end
    end
  end

  seen[value] = nil
  return result
end

local function copy_table(value)
  return copy_value(value, {}, 0)
end

local function get_modname(itemname)
  return itemname:match("^([^:]+):") or "unknown"
end

local function has_armor_groups(groups)
  if type(groups) ~= "table" then
    return false
  end

  for group, value in pairs(groups) do
    if group:match("^armor_") and type(value) == "number" and value ~= 0 then
      return true
    end
  end

  return false
end

local function has_weapon_damage(definition)
  local capabilities = definition.tool_capabilities
  if type(capabilities) ~= "table" or type(capabilities.damage_groups) ~= "table" then
    return false
  end

  return next(capabilities.damage_groups) ~= nil
end

local function classify_item(itemname, definition)
  local groups = definition.groups or {}

  if has_armor_groups(groups) then
    return "armor"
  end

  if definition.type == "tool" then
    if has_weapon_damage(definition) or groups.weapon then
      return "weapon_or_tool"
    end
    return "tool"
  end

  if groups.weapon then
    return "weapon"
  end

  if groups.food or groups.eatable then
    return "food"
  end

  return "item"
end

local function export_items()
  local items = {}

  for itemname, definition in pairs(core.registered_items) do
    local record = {
      name = itemname,
      mod = get_modname(itemname),
      category = classify_item(itemname, definition),
      description = definition.description,
      short_description = definition.short_description,
      type = definition.type,
      groups = copy_table(definition.groups or {}),
      inventory_image = definition.inventory_image,
      wield_image = definition.wield_image,
      stack_max = definition.stack_max,
      tool_capabilities = copy_table(definition.tool_capabilities),
      damage_groups = copy_table(definition.damage_groups),
      armor_groups = copy_table(definition.armor_groups),
      _doc_items_longdesc = definition._doc_items_longdesc,
      _doc_items_usagehelp = definition._doc_items_usagehelp,
    }

    items[#items + 1] = record
  end

  table.sort(items, function(a, b)
    return a.name < b.name
  end)

  return items
end

local function export_entities()
  local entities = {}

  for entityname, definition in pairs(core.registered_entities) do
    local properties = definition.initial_properties or {}
    entities[#entities + 1] = {
      name = entityname,
      mod = get_modname(entityname),
      description = definition.description,
      hp_min = definition.hp_min,
      hp_max = definition.hp_max,
      initial_properties = {
        hp_max = properties.hp_max,
        physical = properties.physical,
        collisionbox = copy_table(properties.collisionbox),
        damage_texture_modifier = properties.damage_texture_modifier,
      },
      damage = definition.damage,
      armor_groups = copy_table(properties.armor_groups),
      drops = copy_table(definition.drops),
    }
  end

  table.sort(entities, function(a, b)
    return a.name < b.name
  end)

  return entities
end

local function export_crafts()
  local crafts = {}

  for _, definition in ipairs(core.registered_crafts) do
    crafts[#crafts + 1] = copy_table(definition)
  end

  return crafts
end

local function write_export()
  local data = {
    schema_version = 1,
    generated_at = os.date("!%Y-%m-%dT%H:%M:%SZ"),
    game = core.get_game_info and core.get_game_info() or nil,
    items = export_items(),
    entities = export_entities(),
    crafts = export_crafts(),
  }

  local json = core.write_json(data, true)
  if not json then
    log("error", "Could not encode export as JSON")
    return false
  end

  local file, error_message = io.open(output_file, "w")
  if not file then
    log("error", "Could not open " .. output_file .. " for writing: " .. tostring(error_message))
    return false
  end

  file:write(json)
  file:close()

  log("action", "Exported " .. #data.items .. " items, " .. #data.entities .. " entities, and " .. #data.crafts .. " recipes to " .. output_file)
  return true
end

core.register_on_mods_loaded(function()
  log("action", "All mods have finished registering; collecting game information")
  write_export()
end)

core.register_chatcommand("jc_information_export", {
  description = "Regenerate the JustCraft item and recipe data export",
  privs = { server = true },
  func = function(name)
    if write_export() then
      return true, "JustCraft information export completed."
    end
    return false, "Export failed. Check the server log."
  end,
})
