-- init.lua
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

  for itemname, definition in pairs(core.registered_items or {}) do
    items[#items + 1] = {
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
  end

  table.sort(items, function(a, b)
    return a.name < b.name
  end)

  return items
end

local function export_entities()
  local entities = {}

  for entityname, definition in pairs(core.registered_entities or {}) do
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

local function get_recipe_time(method, itemname, expected_output)
  if type(core.get_craft_result) ~= "function" or type(ItemStack) ~= "function" then
    return nil
  end

  local ok, output = pcall(core.get_craft_result, {
    method = method,
    width = 1,
    items = { ItemStack(itemname) },
  })

  if not ok or type(output) ~= "table" then
    return nil
  end

  if type(output.time) ~= "number" or output.time <= 0 then
    return nil
  end

  if expected_output then
    local result = ItemStack(output.item or "")
    if result:is_empty() then
      return nil
    end

    local expected = ItemStack(expected_output)
    if result:get_name() ~= expected:get_name() then
      return nil
    end
  end

  return output.time
end

local function get_group_members(group_name)
  local members = {}

  for itemname, definition in pairs(core.registered_items or {}) do
    local groups = definition.groups or {}

    if (groups[group_name] or 0) > 0 then
      members[#members + 1] = itemname
    end
  end

  table.sort(members)
  return members
end

local function export_crafts()
  local crafts = {}
  local seen = {}

  if type(core.get_all_craft_recipes) ~= "function" then
    log("error", "This Luanti version does not provide get_all_craft_recipes(); recipes were not exported")
    return crafts
  end

  local function add_recipe(record)
    local key = core.write_json(record, false)

    if key and not seen[key] then
      seen[key] = true
      crafts[#crafts + 1] = record
    end
  end

  for itemname in pairs(core.registered_items or {}) do
    local recipes = core.get_all_craft_recipes(itemname)

    if type(recipes) == "table" then
      for _, definition in ipairs(recipes) do
        local record = copy_table(definition) or {}
        record.output_item = itemname

        if record.method == "normal" then
          record.recipe_width = record.width
        end

        record.width = nil

        if record.method == "cooking" then
          local input = type(record.items) == "table" and record.items[1] or nil
          local time = nil

          if type(input) == "string" and input ~= "" then
            if input:match("^group:") then
              local group_name = input:sub(7)

              for _, member in ipairs(get_group_members(group_name)) do
                time = get_recipe_time("cooking", member, itemname)

                if time then
                  record.cook_input = member
                  break
                end
              end
            else
              time = get_recipe_time("cooking", input, itemname)

              if time then
                record.cook_input = input
              end
            end
          end

          record.cook_time_seconds = time

        elseif record.method == "fuel" then
          record.burn_time_seconds = record.time
        end

        record.time = nil
        add_recipe(record)
      end
    end
  end

  -- Find fuel recipes even on versions that do not return them
  -- through get_all_craft_recipes().
  for itemname in pairs(core.registered_items or {}) do
    local time = get_recipe_time("fuel", itemname)

    if time then
      add_recipe({
        method = "fuel",
        output_item = "",
        items = { itemname },
        burn_time_seconds = time,
      })
    end
  end

  table.sort(crafts, function(a, b)
    local a_output = a.output_item or ""
    local b_output = b.output_item or ""

    if a_output == b_output then
      if (a.method or "") == (b.method or "") then
        return core.write_json(a, false) < core.write_json(b, false)
      end

      return (a.method or "") < (b.method or "")
    end

    return a_output < b_output
  end)

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

-- Automatically export once every mod has finished registering.
core.register_on_mods_loaded(function()
  log("action", "All mods have finished registering; generating information export")
  write_export()
end)

-- Allow administrators to regenerate the export manually.
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
