function Initialize()
    dofile(SKIN:ReplaceVariables("#@#rm_bangs.lua"))
    CurrentPath = GetVar("CURRENTPATH")
    local lastX, lastY = -1, -1
    local idleTimer = 0
    local threshold = 30
    GetNotification()
end

function CheckMouseMovement()
    local currentX, currentY = tonumber(), tonumber()
    end

function GetNotification()
    local f = io.open(CurrentPath .. "notif.txt")
    if not f then print("File does not exist: \"" .. CurrentPath .. "\"") return end
    local notifLines = f:read("*all")
    f:close()
    if notifLines == "" then
        SKIN:Bang("!DeactivateConfig", "birds\\Notify")
        print("No new notifications")
    return end
    print(notifLines)
    SKIN:Bang("!SetOption", "NotificationText", "Text", notifLines)
    SKIN:Bang("!ShowMeterGroup", "Notification")
    SKIN:Bang("!UpdateMeterGroup", "Notification")
    SKIN:Bang("!Redraw", "#CURRENTCONFIG#")
end