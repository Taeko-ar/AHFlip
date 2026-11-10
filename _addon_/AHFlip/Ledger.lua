-- Ledger tracking: logs your AH buyouts and vendor sales to AHFlipDB.ledger; ah.py imports them into the ledger.
-- Entry format: "time.n:kind:itemID:qty:unitPrice:vendorSellPrice:name" (copper; kind buy|sell).
-- Event flow (checked in game with a probe, Nov 2026):
--   item buyout:  ITEM_SEARCH_RESULTS_UPDATED (listing info) -> PlaceBid(auctionID, amount) -> AUCTION_HOUSE_PURCHASE_COMPLETED(auctionID)
--   stackable:    StartCommoditiesPurchase(item, qty) -> COMMODITY_PRICE_UPDATED(unit, total) -> ConfirmCommoditiesPurchase -> COMMODITY_PURCHASE_SUCCEEDED
--   vendor sale:  PLAYER_MONEY rises while a merchant is open; the item is the newest buyback entry.
--   auction sold: the "Auction successful" mail's invoice (GetInboxInvoiceInfo), read when the mailbox opens.
-- itemID 0 = unknown (a sold item the game can't look up by name); ah.py then matches the name.

local MAX = 2000 -- oldest entries dropped beyond this; ah.py imports on every reload, so nothing is lost

local _, ns = ... -- options from Options.lua: trackBuys, trackSells, trackAuctionSales, chat, debug
local GetItemInfo = C_Item and C_Item.GetItemInfo or GetItemInfo -- Forever has no global GetItemInfo

local seq = 0
-- opt: the option that must be on (default by kind); fallbackName: used when the item id is unknown.
local function record(kind, item, qty, unit, opt, fallbackName)
  if not ns.get(opt or (kind == "buy" and "trackBuys" or "trackSells")) then return end
  local name, _, _, _, _, _, _, _, _, _, sell = GetItemInfo(item)
  name = name or fallbackName
  seq = seq + 1
  local entry = ("%d.%d:%s:%d:%d:%d:%s:%s"):format(time(), seq, kind, item, qty, unit, sell or "", ((name or ""):gsub("[:\"]", "")))
  AHFlipDB.ledger = AHFlipDB.ledger or {}
  table.insert(AHFlipDB.ledger, entry)
  while #AHFlipDB.ledger > MAX do table.remove(AHFlipDB.ledger, 1) end
  if not ns.get("chat") then return end
  DEFAULT_CHAT_FRAME:AddMessage(("|cff33ff99AHFlip|r ledger: %s %dx %s at %s each"):format(
    kind, qty, name or item, GetCoinTextureString and GetCoinTextureString(unit) or unit))
end

local function note(s, always) -- always: errors show even with chat lines off
  if always or ns.get("chat") then DEFAULT_CHAT_FRAME:AddMessage("|cff33ff99AHFlip|r ledger: " .. s) end
end

-- Item (non-stackable) buyouts. PlaceBid is also called for plain bids; those don't fire
-- AUCTION_HOUSE_PURCHASE_COMPLETED, so only won buyouts are logged.
local listings, pending = {}, {} -- auctionID -> {item, qty}; auctionID -> {item, qty, amount}
hooksecurefunc(C_AuctionHouse, "PlaceBid", function(id, amount)
  local l = listings[id]
  if l then pending[id] = { item = l.item, qty = l.qty, amount = amount } end
end)

-- Stackable (commodity) buys.
local commodity
hooksecurefunc(C_AuctionHouse, "StartCommoditiesPurchase", function(item, qty)
  commodity = { item = item, qty = qty }
end)
hooksecurefunc(C_AuctionHouse, "ConfirmCommoditiesPurchase", function(item, qty)
  if commodity and commodity.item == item then commodity.qty = qty end
end)

local merchant, money = false, 0
local function vendorSale(delta)
  if not ns.get("trackSells") then return end
  local n = GetNumBuybackItems()
  local link, price, qty
  if n > 0 then
    link = GetBuybackItemLink(n)
    price, qty = select(3, GetBuybackItemInfo(n))
  end
  local item = link and tonumber(link:match("item:(%d+)"))
  -- shortcut: reads only the newest buyback entry, so very fast multi-item selling can miss some;
  -- upgrade to matching the whole buyback list if the "not logged" message shows up often.
  if item and price == delta and qty and qty > 0 then
    record("sell", item, qty, math.floor(delta / qty + 0.5))
  else
    note(("vendor sale of %dc not logged (could not match it to the buyback list)"):format(delta))
  end
end

-- Sold auctions. Each "Auction successful" mail is logged once, the first time it shows in the mailbox.
-- A mail is told apart by item, count, price and expiry minute (its expiry = now + days left); counts per key
-- allow several identical sales. Seen keys live in AHFlipDB.mailSeen until the mail would have expired.
local mailboxOpen = false

local function saleKey(seen, sig, expiry)
  local m = math.floor(expiry / 60 + 0.5)
  for _, k in ipairs({ m, m - 1, m + 1 }) do -- days left is a float: allow a minute of rounding drift
    if seen[sig .. "@" .. k] then return sig .. "@" .. k end
  end
  return sig .. "@" .. m
end

local function itemIdByName(name)
  local link = select(2, GetItemInfo(name)) -- works for items this game client has loaded (you had it)
  return link and tonumber(link:match("item:(%d+)")) or 0
end

local function mailSales()
  if not (mailboxOpen and ns.get("trackAuctionSales") and GetInboxInvoiceInfo) then return end
  AHFlipDB.mailSeen = AHFlipDB.mailSeen or {}
  local seen, now, found, sales = AHFlipDB.mailSeen, time(), {}, {}
  for i = 1, GetInboxNumItems() do
    local kind, itemName, _, bid, _, _, cut, _, _, count = GetInboxInvoiceInfo(i)
    local subject, _, _, daysLeft = select(4, GetInboxHeaderInfo(i))
    if kind == "seller" and itemName and bid and daysLeft then
      count = (count and count > 0) and count or 1
      local key = saleKey(seen, ("%s|%d|%d"):format(itemName, count, bid), now + daysLeft * 86400)
      found[key] = (found[key] or 0) + 1
      sales[key] = { name = itemName, count = count, got = bid - (cut or 0) }
    elseif ns.get("debug") and subject and AUCTION_SOLD_MAIL_SUBJECT
        and subject:find(AUCTION_SOLD_MAIL_SUBJECT:gsub("%%s", ""), 1, true) then
      note("sale mail without invoice data: " .. subject, true)
    end
  end
  for key, n in pairs(found) do
    local s = sales[key]
    for _ = (seen[key] or 0) + 1, n do -- only mails not logged before
      record("sell", itemIdByName(s.name), s.count, math.floor(s.got / s.count + 0.5), "trackAuctionSales", s.name)
    end
    seen[key] = math.max(seen[key] or 0, n)
  end
  for key in pairs(seen) do -- forget mails past their expiry
    if tonumber(key:match("@(%-?%d+)$")) * 60 < now then seen[key] = nil end
  end
end

local f = CreateFrame("Frame")
for _, e in ipairs({ "ITEM_SEARCH_RESULTS_UPDATED", "ITEM_SEARCH_RESULTS_ADDED", "AUCTION_HOUSE_PURCHASE_COMPLETED",
  "COMMODITY_PRICE_UPDATED", "COMMODITY_PURCHASE_SUCCEEDED", "COMMODITY_PURCHASE_FAILED",
  "PLAYER_MONEY", "PLAYER_ENTERING_WORLD", "MERCHANT_SHOW", "MERCHANT_CLOSED",
  "MAIL_SHOW", "MAIL_CLOSED", "MAIL_INBOX_UPDATE" }) do
  pcall(f.RegisterEvent, f, e) -- pcall: unknown events error on some clients
end

local onEvent
f:SetScript("OnEvent", function(...)
  -- errors go to chat too, in case an error addon swallows them
  local ok, err = pcall(onEvent, ...)
  if not ok then note("error: " .. tostring(err), true) end
end)

function onEvent(_, e, a, b)
  if e == "PLAYER_ENTERING_WORLD" and ns.get("debug") then note("tracking on", true) end
  if e == "ITEM_SEARCH_RESULTS_UPDATED" or e == "ITEM_SEARCH_RESULTS_ADDED" then
    if type(a) ~= "table" then return end
    for i = 1, C_AuctionHouse.GetNumItemSearchResults(a) do
      local r = C_AuctionHouse.GetItemSearchResultInfo(a, i)
      if r and r.auctionID then listings[r.auctionID] = { item = a.itemID, qty = r.quantity or 1 } end
    end
  elseif e == "AUCTION_HOUSE_PURCHASE_COMPLETED" then
    local p = pending[a] -- a is 0 after a commodity buy; that one is logged below
    if p then
      pending[a] = nil
      record("buy", p.item, p.qty, math.floor(p.amount / p.qty + 0.5))
    elseif a and a ~= 0 and ns.get("trackBuys") then
      note("a purchase was not logged (its listing was not seen; buy from the item's listing page)")
    end
  elseif e == "COMMODITY_PRICE_UPDATED" then
    if commodity then commodity.total = b end
  elseif e == "COMMODITY_PURCHASE_SUCCEEDED" then
    local c = commodity
    commodity = nil
    if c and c.total and c.qty and c.qty > 0 then
      record("buy", c.item, c.qty, math.floor(c.total / c.qty + 0.5))
    elseif ns.get("trackBuys") then
      note("a stackable purchase was not logged (price unknown)")
    end
  elseif e == "COMMODITY_PURCHASE_FAILED" then
    commodity = nil
  elseif e == "PLAYER_ENTERING_WORLD" then
    money = GetMoney()
  elseif e == "MERCHANT_SHOW" or e == "MERCHANT_CLOSED" then
    merchant, money = e == "MERCHANT_SHOW", GetMoney()
  elseif e == "MAIL_SHOW" or e == "MAIL_CLOSED" then
    mailboxOpen = e == "MAIL_SHOW"
  elseif e == "MAIL_INBOX_UPDATE" then
    mailSales()
  elseif e == "PLAYER_MONEY" then
    local now = GetMoney()
    local delta = now - money
    money = now
    -- the buyback list may update just after the money; read it a moment later
    if merchant and delta > 0 then C_Timer.After(0.3, function() vendorSale(delta) end) end
  end
end
