-- HD2-Addon: mods/example/health_readout
-- An example for tools/fakegame.py: your Helldiver's health as text, read from the network objects with the checks
-- that keep the game alive, and a key to hide it. See test_health_readout.py and docs/TESTING.md.
local chef = ...

-- The engine knows a type or a field by the 32-bit hash of its name, so any string with that hash works as the name.
-- The player type 803159b3, the Helldiver type 5d9752f9 and the player's avatar field 0f27c68e have no known real
-- names; these strings were found for them with tools/crack_thin.c. health and max_health are real names.
local PLAYER, HELLDIVER, AVATAR = 'un6y1d', 'vvhx8ga', 'u4d1h9a'
local NO_OBJECT = 32767

local M = { version = '1.0.0' }
local shown = chef.option('shown', { type = 'toggle', label = 'Show health', default = true,
                                     hint = 'Your health as a number at the bottom left of the screen.' })
chef.on_change('shown', function(v) shown = v end)
local hide = chef.bind('hide', 'f6', 'Hide while held')

local mine = nil                     -- your player object's id, found once a world
local world = nil

-- an object read only after it was checked the same frame: a field of an object that is gone ends the game
local function alive(s, id, type_name)
  return chef.call('GameSession.game_object_exists', s, id) == true
     and chef.call('GameSession.game_object_is_type', s, id, type_name) == true
end

local function find_player(s)
  local ids = chef.call('GameSession.objects_owned_by', s, chef.call('Network.peer_id'))
  for _, id in ipairs(ids or {}) do
    if chef.call('GameSession.game_object_is_type', s, id, PLAYER) == true then return id end
  end
  return nil
end

function M.update(dt)
  if chef.world_id() ~= world then world, mine = chef.world_id(), nil end    -- object ids start over in a new world
  if not shown or hide.down() then return end
  local s = chef.call('Network.game_session')
  if not s then return end
  if not (mine and alive(s, mine, PLAYER)) then
    mine = find_player(s)
    if not (mine and alive(s, mine, PLAYER)) then return end
  end
  local body = chef.call('GameSession.game_object_field', s, mine, AVATAR)
  if type(body) ~= 'number' or body == NO_OBJECT or not alive(s, body, HELLDIVER) then return end
  local hp = chef.call('GameSession.game_object_field', s, body, 'health')
  local most = chef.call('GameSession.game_object_field', s, body, 'max_health')
  if type(hp) ~= 'number' or type(most) ~= 'number' or most <= 0 then return end
  local c = hp < most * 0.3 and chef.color(255, 80, 60, 255) or chef.color(240, 230, 210, 255)   -- (made this frame)
  chef.text(40, 40, string.format('HP %d', hp), 3, c, 905)
end

return M
