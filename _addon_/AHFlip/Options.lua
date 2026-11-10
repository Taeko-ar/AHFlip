-- AHFlip options: defaults, the settings window (/ahflip settings), the minimap button and an entry in
-- the game's own AddOns options. Loaded first (see AHFlip.toc); the other files read options with ns.get.
local _, ns = ...

ns.DEFAULTS = {
  scanButton = true,   -- scan button above the AH window
  cooldownText = true, -- "Ready in m:ss" on the button during the 15-min cooldown
  trackBuys = true,    -- log AH purchases to the ledger
  trackSells = true,   -- log vendor sales to the ledger
  trackAuctionSales = true, -- log your sold auctions (from the sale mails) to the ledger
  chat = false,        -- chat line for each logged trade
  minimap = true,
  minimapAngle = 220,  -- degrees around the minimap
  debug = false,       -- raw scan rows for test items (AHFlipDB.debug) and a "tracking on" line at login
}

ns.applyFns = {} -- called after any option changes, so each file can update its UI

function ns.get(k)
  local o = AHFlipDB and AHFlipDB.opt
  if o and o[k] ~= nil then return o[k] end
  return ns.DEFAULTS[k]
end

function ns.set(k, v)
  AHFlipDB.opt = AHFlipDB.opt or {}
  AHFlipDB.opt[k] = v
  for _, fn in ipairs(ns.applyFns) do fn() end
end

-- Settings window -------------------------------------------------------------------------------

local OPTIONS = { -- {key, label, tooltip} or {header}
  { "Auction house scan" },
  { "scanButton", "Show the scan button on the auction house", "Off: scan with /ahflip instead." },
  { "cooldownText", "Show the cooldown countdown on the button", "Off: the button just stays greyed out until the next scan is allowed." },
  { "Ledger tracking (sent to the website on /reload)" },
  { "trackBuys", "Track auction house purchases" },
  { "trackSells", "Track vendor sales" },
  { "trackAuctionSales", "Track sold auctions", "Read from the \"Auction successful\" mails when you open the mailbox: price after the AH cut." },
  { "chat", "Chat line for every logged trade", "Also hides the \"not logged\" notes. Errors always show." },
  { "Other" },
  { "minimap", "Show the minimap button", "Off: open this window with /ahflip settings." },
  { "debug", "Debug mode", "Saves raw scan rows for a few test items (AHFlipDB.debug), prints \"tracking on\" at login and notes sale mails it can't read." },
}

local panel, checks = nil, {}

local function refreshChecks()
  for k, cb in pairs(checks) do cb:SetChecked(ns.get(k)) end
end

local function buildPanel()
  panel = CreateFrame("Frame", "AHFlipSettings", UIParent, "BasicFrameTemplateWithInset")
  panel:SetPoint("CENTER")
  panel:SetFrameStrata("DIALOG")
  panel:SetClampedToScreen(true)
  panel:EnableMouse(true)
  panel:SetMovable(true)
  panel:RegisterForDrag("LeftButton")
  panel:SetScript("OnDragStart", panel.StartMoving)
  panel:SetScript("OnDragStop", panel.StopMovingOrSizing)
  panel:SetScript("OnShow", refreshChecks)
  panel:Hide()
  tinsert(UISpecialFrames, "AHFlipSettings") -- Esc closes it

  local title = panel.TitleText or panel:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
  if not panel.TitleText then title:SetPoint("TOP", 0, -5) end
  title:SetText("AHFlip settings")

  local y = -34
  for _, o in ipairs(OPTIONS) do
    if #o == 1 then
      local fs = panel:CreateFontString(nil, "OVERLAY", "GameFontNormal")
      fs:SetPoint("TOPLEFT", 16, y - 6)
      fs:SetText(o[1])
      y = y - 28
    else
      local key, text, tip = o[1], o[2], o[3]
      local cb = CreateFrame("CheckButton", nil, panel, "UICheckButtonTemplate")
      cb:SetSize(26, 26)
      cb:SetPoint("TOPLEFT", 20, y)
      local fs = panel:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
      fs:SetPoint("LEFT", cb, "RIGHT", 4, 0)
      fs:SetText(text)
      cb:SetScript("OnClick", function(self) ns.set(key, self:GetChecked() and true or false) end)
      if tip then
        cb:SetScript("OnEnter", function(self)
          GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
          GameTooltip:AddLine(text)
          GameTooltip:AddLine(tip, 1, 1, 1, true)
          GameTooltip:Show()
        end)
        cb:SetScript("OnLeave", GameTooltip_Hide)
      end
      checks[key] = cb
      y = y - 26
    end
  end

  local help = panel:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
  help:SetPoint("TOPLEFT", 16, y - 12)
  help:SetJustifyH("LEFT")
  help:SetText("/ahflip  full scan (auction house open)\n/ahflip settings  this window\nMinimap button: click opens this window, drag moves it.")
  panel:SetSize(400, -y + 70)
end

function ns.toggleSettings()
  if not panel then buildPanel() end
  panel:SetShown(not panel:IsShown())
end

-- Minimap button ----------------------------------------------------------------------------------

local mm

local function placeMinimap()
  local a = math.rad(ns.get("minimapAngle"))
  local r = Minimap:GetWidth() / 2 + 5
  mm:ClearAllPoints()
  mm:SetPoint("CENTER", Minimap, "CENTER", math.cos(a) * r, math.sin(a) * r)
end

local function buildMinimap()
  mm = CreateFrame("Button", "AHFlipMinimapButton", Minimap)
  mm:SetSize(31, 31)
  mm:SetFrameStrata("MEDIUM")
  mm:SetFrameLevel(8)
  mm:RegisterForClicks("AnyUp")
  mm:RegisterForDrag("LeftButton")
  mm:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")
  local icon = mm:CreateTexture(nil, "BACKGROUND")
  icon:SetTexture("Interface\\Icons\\INV_Misc_Coin_02")
  icon:SetSize(20, 20)
  icon:SetPoint("TOPLEFT", 7, -5)
  local border = mm:CreateTexture(nil, "OVERLAY")
  border:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")
  border:SetSize(53, 53)
  border:SetPoint("TOPLEFT")
  mm:SetScript("OnClick", function() ns.toggleSettings() end)
  mm:SetScript("OnDragStart", function(self)
    self:SetScript("OnUpdate", function()
      local mx, my = Minimap:GetCenter()
      local px, py = GetCursorPosition()
      local s = Minimap:GetEffectiveScale()
      AHFlipDB.opt = AHFlipDB.opt or {}
      AHFlipDB.opt.minimapAngle = math.deg(math.atan2(py / s - my, px / s - mx))
      placeMinimap()
    end)
  end)
  mm:SetScript("OnDragStop", function(self) self:SetScript("OnUpdate", nil) end)
  mm:SetScript("OnEnter", function(self)
    GameTooltip:SetOwner(self, "ANCHOR_LEFT")
    GameTooltip:AddLine("AHFlip")
    GameTooltip:AddLine("Click: settings", 1, 1, 1)
    GameTooltip:AddLine("Drag: move", 1, 1, 1)
    GameTooltip:Show()
  end)
  mm:SetScript("OnLeave", GameTooltip_Hide)
end

local function updateMinimap()
  if ns.get("minimap") then
    if not mm then buildMinimap() end
    placeMinimap()
    mm:Show()
  elseif mm then
    mm:Hide()
  end
end
table.insert(ns.applyFns, updateMinimap)
table.insert(ns.applyFns, function() if panel and panel:IsShown() then refreshChecks() end end)

-- Entry in the game's options (Esc > Options > AddOns) that opens the window above.
local function registerBlizzardOptions()
  local stub = CreateFrame("Frame")
  stub.name = "AHFlip"
  local b = CreateFrame("Button", nil, stub, "UIPanelButtonTemplate")
  b:SetSize(200, 24)
  b:SetPoint("TOPLEFT", 16, -16)
  b:SetText("Open AHFlip settings")
  b:SetScript("OnClick", function()
    if SettingsPanel and SettingsPanel:IsShown() then HideUIPanel(SettingsPanel) end
    if InterfaceOptionsFrame and InterfaceOptionsFrame:IsShown() then HideUIPanel(InterfaceOptionsFrame) end
    if not (panel and panel:IsShown()) then ns.toggleSettings() end
  end)
  if Settings and Settings.RegisterCanvasLayoutCategory then
    Settings.RegisterAddOnCategory(Settings.RegisterCanvasLayoutCategory(stub, "AHFlip"))
  elseif InterfaceOptions_AddCategory then
    InterfaceOptions_AddCategory(stub)
  end
end

local f = CreateFrame("Frame")
f:RegisterEvent("PLAYER_LOGIN") -- SavedVariables are loaded by now
f:SetScript("OnEvent", function()
  updateMinimap()
  pcall(registerBlizzardOptions) -- optional; the options API differs between clients
end)
