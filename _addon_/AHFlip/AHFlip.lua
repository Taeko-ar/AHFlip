-- AHFlip: one-click full auction house scan for ah.py (Blizzard's replicate scan: every listing).
-- Per item it keeps the cheapest listing you can actually buy out: skips bid-locked listings
-- (bid >= buyout, the game refuses buyout) and your own. Then reloads the UI so WoW writes
-- AHFlipDB to SavedVariables/AHFlip.lua, which ah.py imports.
--
-- AHFlipDB.items format: "itemID:buyableQty:price,qty,price,qty,...;..." with the LEVELS cheapest unit
-- buyout prices (copper) ascending, each with the buyable quantity at that price.

AHFlipDB = AHFlipDB or {}
local _, ns = ... -- shared with Options.lua (ns.get reads options)

local COOLDOWN = 15 * 60 -- Blizzard allows one replicate scan per 15 minutes
local BATCH = 2000       -- listings processed per frame
local TIMEOUT = 120      -- seconds to wait for the server's data
local LEVELS = 20        -- cheapest price levels saved per item
-- Raw replicate rows saved for these items (AHFlipDB.debug) to check how stackables report buyout.
-- Minor Mana Oil, Peacebloom, Light Leather, Copper Ore.
local DEBUG_ITEMS = { [20745] = true, [2447] = true, [2318] = true, [2770] = true }

local frame = CreateFrame("Frame")
local scanning = false -- true from request until saved/cancelled
local waiting = false  -- true until the server's data arrives
local pendingReload = false -- scan done, waiting for the user's click to reload (saves to disk)
local button

local function msg(s)
  DEFAULT_CHAT_FRAME:AddMessage("|cff33ff99AHFlip|r: " .. s) -- not print(): it shows nothing on some setups
end

local function setLabel(s)
  if button then button:SetText(s) end
end

-- Loading indicator: the button is disabled and shows elapsed time / progress, updated 4x per second.
local ticker, startedAt, progress = nil, 0, 0

local function startIndicator()
  startedAt, progress = time(), 0
  if button then button:Disable() end
  local n = 0
  ticker = C_Timer.NewTicker(0.25, function()
    n = n + 1
    local dots = string.rep(".", n % 4)
    if waiting then
      setLabel(("Waiting for server%s %ds"):format(dots, time() - startedAt))
    else
      setLabel(("Processing %d%%%s"):format(progress, dots))
    end
  end)
end

local function stopIndicator(label)
  if ticker then
    ticker:Cancel()
    ticker = nil
  end
  if button then button:Enable() end
  setLabel(label)
end

local GetItemInfo = C_Item and C_Item.GetItemInfo or GetItemInfo -- Forever has no global GetItemInfo
local scanSide = "horde" -- which auction house the running scan is from

-- Side of the auction house being used: the auctioneer's faction; goblin (Blackwater) auctioneers are neutral.
local function auctionSide()
  if not UnitExists("npc") then return (UnitFactionGroup("player") or "Horde"):lower() end
  local f = UnitFactionGroup("npc")
  if f == "Horde" or f == "Alliance" then return f:lower() end
  return "goblin"
end

-- "id:vendorPrice:name;..." for every scanned item; ah.py uses it for items the Blizzard API has no info for.
local function nameEntry(id, name)
  local sell = select(11, GetItemInfo(id)) -- nil until the game has loaded the item
  return id .. ":" .. (sell or "") .. ":" .. (name:gsub("[;\"\\]", ""))
end

local function namesString(names)
  local out = {}
  for id, name in pairs(names) do out[#out + 1] = nameEntry(id, name) end
  return table.concat(out, ";")
end

-- The scan has no name for items this game client never loaded. Ask the game to load them; each name is
-- added to AHFlipDB.names when it arrives and saved with the next reload. Arrival is signalled by
-- ITEM_DATA_LOAD_RESULT or GET_ITEM_INFO_RECEIVED depending on the client, so both are watched, and a
-- once-a-second sweep (for NAME_WAIT seconds) catches any the events miss.
local NAME_WAIT = 30
local missingNames, nameTicker = {}, nil
local LOAD_EVENTS = { "ITEM_DATA_LOAD_RESULT", "GET_ITEM_INFO_RECEIVED" }

local function stopNames()
  for _, e in ipairs(LOAD_EVENTS) do pcall(frame.UnregisterEvent, frame, e) end
  if nameTicker then nameTicker:Cancel() end
  nameTicker = nil
end

local function nameArrived(id)
  if not missingNames[id] then return end
  local name = GetItemInfo(id)
  if not name then return end
  missingNames[id] = nil
  AHFlipDB.names = (AHFlipDB.names ~= "" and AHFlipDB.names .. ";" or "") .. nameEntry(id, name)
  if not next(missingNames) then
    stopNames()
    msg("all item names loaded; reload to save.")
  end
end

local function requestNames(items, names)
  local n = 0
  for id in pairs(items) do
    if not names[id] then
      missingNames[id] = true
      n = n + 1
      if C_Item and C_Item.RequestLoadItemDataByID then C_Item.RequestLoadItemDataByID(id) end
      GetItemInfo(id) -- also asks the game to load the item
    end
  end
  if n == 0 then return 0 end
  for _, e in ipairs(LOAD_EVENTS) do pcall(frame.RegisterEvent, frame, e) end -- pcall: unknown events error
  nameTicker = C_Timer.NewTicker(1, function()
    for id in pairs(missingNames) do nameArrived(id) end
  end, NAME_WAIT)
  C_Timer.After(NAME_WAIT + 0.5, function()
    local left = 0
    for _ in pairs(missingNames) do left = left + 1 end
    if left > 0 then msg(("%d item names didn't load; they'll be retried on the next scan."):format(left)) end
    missingNames = {}
    stopNames()
  end)
  return n
end

local function finish(items, total, locked, own, names)
  local parts = {}
  for id, levels in pairs(items) do
    local prices, qty = {}, 0 -- qty: buyable units of this item
    for p, q in pairs(levels) do
      prices[#prices + 1] = p
      qty = qty + q
    end
    table.sort(prices)
    local out = {}
    for k = 1, math.min(LEVELS, #prices) do
      out[#out + 1] = prices[k] .. "," .. levels[prices[k]]
    end
    parts[#parts + 1] = id .. ":" .. qty .. ":" .. table.concat(out, ",")
  end
  AHFlipDB.time = time()
  AHFlipDB.realm = GetRealmName()
  AHFlipDB.faction = UnitFactionGroup("player")
  AHFlipDB.listings = total
  AHFlipDB.items = table.concat(parts, ";")
  AHFlipDB.ah = scanSide
  AHFlipDB.names = namesString(names)
  local loading = requestNames(items, names)
  -- ReloadUI is protected: only allowed from a click/keypress, so the button turns into "Reload to save".
  msg(("scanned %d items on the %s auction house from %d listings (skipped %d bid-locked, %d yours). Click \"Reload to save\" or type /reload."):format(#parts, scanSide, total, locked, own))
  if loading > 0 then
    msg(("loading the names of %d items the game didn't know yet; wait for \"all item names loaded\" (up to 30 s) before reloading."):format(loading))
  end
  stopIndicator("Reload to save")
  scanning = false
  pendingReload = true
end

local function process()
  local total = C_AuctionHouse.GetNumReplicateItems()
  local me = UnitName("player")
  local items, locked, own, i, names = {}, 0, 0, 0, {}
  local debug = ns.get("debug")
  if debug then AHFlipDB.debug = {} end -- off: keep the last debug capture
  local function step()
    if not scanning then return end -- AH closed meanwhile
    local stop = math.min(i + BATCH, total)
    for idx = i, stop - 1 do
      local name, _, count, _, _, _, _, minBid, _, buyout, bid, _, _, owner, _, _, itemID = C_AuctionHouse.GetReplicateItemInfo(idx)
      if itemID and name and name ~= "" then names[itemID] = name end
      if debug and itemID and DEBUG_ITEMS[itemID] then
        local rows = AHFlipDB.debug[itemID] or {}
        AHFlipDB.debug[itemID] = rows
        if #rows < 40 then
          rows[#rows + 1] = ("count=%s buyout=%s bid=%s minBid=%s"):format(tostring(count), tostring(buyout), tostring(bid), tostring(minBid))
        end
      end
      if itemID and buyout and buyout > 0 and count and count > 0 then
        if bid and bid > 0 and bid >= buyout then
          locked = locked + 1
        elseif owner and owner == me then
          own = own + 1
        else
          local unit = math.floor(buyout / count)
          local levels = items[itemID]
          if not levels then
            levels = {}
            items[itemID] = levels
          end
          levels[unit] = (levels[unit] or 0) + count
        end
      end
    end
    i = stop
    if i < total then
      progress = math.floor(i * 100 / total)
      C_Timer.After(0, step)
    else
      finish(items, total, locked, own, names)
    end
  end
  step()
end

local function start()
  if pendingReload then return ReloadUI() end -- runs from the click/slash command, so it's allowed
  if scanning then return msg("scan already running") end
  if not (AuctionHouseFrame and AuctionHouseFrame:IsShown()) then return msg("open the auction house first") end
  local wait = (AHFlipDB.lastRequest or 0) + COOLDOWN - time()
  if wait > 0 then
    return msg(("Blizzard allows one full scan per 15 min; try again in %d:%02d"):format(wait / 60, wait % 60))
  end
  scanning, waiting = true, true
  scanSide = auctionSide()
  AHFlipDB.lastRequest = time()
  frame:RegisterEvent("REPLICATE_ITEM_LIST_UPDATE")
  C_AuctionHouse.ReplicateItems()
  startIndicator()
  msg("full scan requested, this can take a minute...")
  local requested = AHFlipDB.lastRequest
  C_Timer.After(TIMEOUT, function()
    if waiting and AHFlipDB.lastRequest == requested then
      -- no data: another addon may have used the 15-min allowance
      scanning, waiting = false, false
      frame:UnregisterEvent("REPLICATE_ITEM_LIST_UPDATE")
      stopIndicator("AHFlip scan")
      msg("no data from the server. Another addon may have run a full scan in the last 15 min; try later.")
    end
  end)
end

-- Idle state of the button: "Ready in m:ss" (disabled) during the 15-min cooldown, else "AHFlip scan".
-- Also applies the scanButton/cooldownText options.
local function refreshIdle()
  if not button then return end
  button:SetShown(ns.get("scanButton"))
  if scanning or pendingReload then return end
  local wait = (AHFlipDB.lastRequest or 0) + COOLDOWN - time()
  if wait > 0 then
    button:Disable()
    setLabel(ns.get("cooldownText") and ("Ready in %d:%02d"):format(wait / 60, wait % 60) or "AHFlip scan")
  else
    button:Enable()
    setLabel("AHFlip scan")
  end
end
table.insert(ns.applyFns, refreshIdle)

local function makeButton()
  if button or not AuctionHouseFrame then return end
  button = CreateFrame("Button", "AHFlipScanButton", AuctionHouseFrame, "UIPanelButtonTemplate")
  button:SetSize(180, 22) -- wide enough for "Waiting for server... 120s"
  button:SetPoint("BOTTOMLEFT", AuctionHouseFrame, "TOPLEFT", 0, 2) -- above the AH window, overlaps nothing
  button:SetScript("OnClick", start)
  C_Timer.NewTicker(1, refreshIdle)
  refreshIdle()
end

frame:SetScript("OnEvent", function(_, event, arg1)
  if event == "GET_ITEM_INFO_RECEIVED" or event == "ITEM_DATA_LOAD_RESULT" then
    nameArrived(arg1)
  elseif event == "AUCTION_HOUSE_SHOW" then
    makeButton()
  elseif event == "REPLICATE_ITEM_LIST_UPDATE" then
    frame:UnregisterEvent("REPLICATE_ITEM_LIST_UPDATE")
    if scanning then
      waiting = false
      msg("data received, processing...")
      process()
    end
  elseif event == "AUCTION_HOUSE_CLOSED" and scanning then
    scanning, waiting = false, false
    frame:UnregisterEvent("REPLICATE_ITEM_LIST_UPDATE")
    stopIndicator("AHFlip scan")
    msg("auction house closed, scan cancelled")
  end
end)
frame:RegisterEvent("AUCTION_HOUSE_SHOW")
frame:RegisterEvent("AUCTION_HOUSE_CLOSED")

SLASH_AHFLIP1 = "/ahflip"
SlashCmdList.AHFLIP = function(arg)
  arg = strtrim((arg or ""):lower())
  if arg == "settings" or arg == "config" or arg == "options" then return ns.toggleSettings() end
  if arg == "help" then return msg("/ahflip: full scan (auction house open) · /ahflip settings: options window") end
  start()
end
