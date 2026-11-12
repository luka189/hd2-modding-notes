-- A line against the scenery boxes of data/scenery_boxes.json (or tools/scenery_boxes.py --lua), in plain Lua 5.1.
-- No engine calls: the caller supplies each unit's pose. See docs/SCENERY.md.
--
--   kind: { box = { hx, hy, hz, cx, cy, cz }, boxes = { { hx, hy, hz, cx, cy, cz [, yaw] }, ... } }
--         as the data has it: metres from the unit's root in the unit's frame (x right, y forward, z up)
--   pose: { x, y, z,                 the unit's root in the world
--           R = { { xx, xy, xz },    the unit's x axis in the world, unit length
--                 { yx, yy, yz },    its y axis
--                 { zx, zy, zz } },  its z axis
--           sx, sy, sz }             the unit's scale along its axes (left out: 1)
local S = {}

-- a world point in the unit's frame, and back
function S.to_local(p, x, y, z)
  local R = p.R
  local dx, dy, dz = x - p.x, y - p.y, z - p.z
  return (R[1][1] * dx + R[1][2] * dy + R[1][3] * dz) / (p.sx or 1),
         (R[2][1] * dx + R[2][2] * dy + R[2][3] * dz) / (p.sy or 1),
         (R[3][1] * dx + R[3][2] * dy + R[3][3] * dz) / (p.sz or 1)
end

function S.to_world(p, lx, ly, lz)
  local R = p.R
  local dx, dy, dz = lx * (p.sx or 1), ly * (p.sy or 1), lz * (p.sz or 1)
  return p.x + R[1][1] * dx + R[2][1] * dy + R[3][1] * dz,
         p.y + R[1][2] * dx + R[2][2] * dy + R[3][2] * dz,
         p.z + R[1][3] * dx + R[2][3] * dy + R[3][3] * dz
end

-- the box round all of a kind's boxes, in the unit's frame: { hx, hy, hz, cx, cy, cz }. Made once a kind (kept in
-- kind.env). From the boxes themselves, not from kind.box: a plate may stand a little outside the mesh.
function S.envelope(kind)
  local e = kind.env
  if e then return e end
  local x0, x1, y0, y1, z0, z1 = math.huge, -math.huge, math.huge, -math.huge, math.huge, -math.huge
  for _, q in ipairs(kind.boxes) do
    local hx, hy = q[1], q[2]
    if q[7] then
      local c, s = math.abs(math.cos(q[7])), math.abs(math.sin(q[7]))
      hx, hy = c * q[1] + s * q[2], s * q[1] + c * q[2]
    end
    x0, x1 = math.min(x0, q[4] - hx), math.max(x1, q[4] + hx)
    y0, y1 = math.min(y0, q[5] - hy), math.max(y1, q[5] + hy)
    z0, z1 = math.min(z0, q[6] - q[3]), math.max(z1, q[6] + q[3])
  end
  e = { (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2, (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2 }
  kind.env = e
  return e
end

-- the envelope's box in the world, axis-aligned, grown by `grow` metres: x0, x1, y0, y1, z0, z1. For a grid of
-- units and for a first test against a segment's own box.
function S.world_box(kind, p, grow)
  local e = S.envelope(kind)
  grow = grow or 0
  local x0, x1, y0, y1, z0, z1 = math.huge, -math.huge, math.huge, -math.huge, math.huge, -math.huge
  for i = 0, 7 do
    local wx, wy, wz = S.to_world(p, e[4] + ((i % 2 == 0) and -e[1] or e[1]),
                                     e[5] + ((math.floor(i / 2) % 2 == 0) and -e[2] or e[2]),
                                     e[6] + ((i < 4) and -e[3] or e[3]))
    x0, x1 = math.min(x0, wx), math.max(x1, wx)
    y0, y1 = math.min(y0, wy), math.max(y1, wy)
    z0, z1 = math.min(z0, wz), math.max(z1, wz)
  end
  return x0 - grow, x1 + grow, y0 - grow, y1 + grow, z0 - grow, z1 + grow
end

-- one axis of the slab test: the part t0..t1 of the segment (start a, direction d) between c - h and c + h
local function slab1(a, d, c, h, t0, t1)
  local lo, hi = c - h, c + h
  if math.abs(d) < 1e-9 then
    if a < lo or a > hi then return nil end
    return t0, t1
  end
  local ta, tb = (lo - a) / d, (hi - a) / d
  if ta > tb then ta, tb = tb, ta end
  if ta > t0 then t0 = ta end
  if tb < t1 then t1 = tb end
  if t0 > t1 then return nil end
  return t0, t1
end

-- the segment a-b (in the unit's frame) against one box q, grown by `grow` on every side: where it enters, as t in
-- (0, 1], or nil. A segment that starts inside the box gives nil: the line was in it already. A box with a seventh
-- number is turned about z by that angle: the segment is turned into the box's frame first.
function S.box_entry(ax, ay, az, bx, by, bz, q, grow)
  grow = grow or 0
  local cx, cy = q[4], q[5]
  local yaw = q[7]
  if yaw then
    local c, s = q[8], q[9]
    if not c then c, s = math.cos(yaw), math.sin(yaw) q[8], q[9] = c, s end
    local dax, day, dbx, dby = ax - cx, ay - cy, bx - cx, by - cy
    ax, ay, bx, by = dax * c + day * s, -dax * s + day * c, dbx * c + dby * s, -dbx * s + dby * c
    cx, cy = 0, 0
  end
  local t0, t1 = slab1(ax, bx - ax, cx, q[1] + grow, 0, 1)
  if not t0 then return nil end
  t0, t1 = slab1(ay, by - ay, cy, q[2] + grow, t0, t1)
  if not t0 then return nil end
  t0, t1 = slab1(az, bz - az, q[6], q[3] + grow, t0, t1)
  if not t0 or t0 <= 0 then return nil end
  return t0
end

-- does the segment a-b (in the unit's frame) touch the plain box q at all? A start inside counts.
function S.touches(ax, ay, az, bx, by, bz, q)
  local t0, t1 = slab1(ax, bx - ax, q[4], q[1], 0, 1)
  if not t0 then return false end
  t0, t1 = slab1(ay, by - ay, q[5], q[2], t0, t1)
  if not t0 then return false end
  return slab1(az, bz - az, q[6], q[3], t0, t1) ~= nil
end

-- the world segment (x1, y1, z1)-(x2, y2, z2) against one unit: where it first enters one of the kind's boxes, as t
-- in (0, 1] along the segment, and that box's place in kind.boxes; or nil. The hit point is the segment's start plus
-- t times its length.
function S.segment(kind, p, x1, y1, z1, x2, y2, z2)
  local ax, ay, az = S.to_local(p, x1, y1, z1)
  local bx, by, bz = S.to_local(p, x2, y2, z2)
  if not S.touches(ax, ay, az, bx, by, bz, S.envelope(kind)) then return nil end
  local best, at
  for i, q in ipairs(kind.boxes) do
    local t = S.box_entry(ax, ay, az, bx, by, bz, q)
    if t and (not best or t < best) then best, at = t, i end
  end
  return best, at
end

return S
