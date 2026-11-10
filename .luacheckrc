-- luacheck config for the WoW addon (_addon_/AHFlip). WoW runs Lua 5.1 plus its own API globals.
std = "lua51"
max_line_length = 200
include_files = { "_addon_/**/*.lua" } -- not the .toc files

-- globals the addon creates or writes
globals = { "AHFlipDB", "SLASH_AHFLIP1", "SlashCmdList" }

-- WoW API the addon reads (add new ones here when the addon starts using them)
read_globals = {
  -- frames and UI
  "CreateFrame", "UIParent", "Minimap", "GameTooltip", "GameTooltip_Hide", "DEFAULT_CHAT_FRAME",
  "UISpecialFrames", "AuctionHouseFrame", "HideUIPanel", "Settings", "SettingsPanel",
  "InterfaceOptionsFrame", "InterfaceOptions_AddCategory", "GetCursorPosition", "ReloadUI",
  -- namespaces
  "C_AuctionHouse", "C_Timer", "C_Item",
  -- units, money, items
  "UnitName", "UnitFactionGroup", "UnitExists", "GetRealmName", "GetMoney", "GetCoinTextureString",
  "GetItemInfo", "GetNumBuybackItems", "GetBuybackItemLink", "GetBuybackItemInfo",
  -- mail
  "GetInboxNumItems", "GetInboxHeaderInfo", "GetInboxInvoiceInfo", "AUCTION_SOLD_MAIL_SUBJECT",
  -- WoW's Lua helpers
  "hooksecurefunc", "time", "date", "tinsert", "strtrim",
}
