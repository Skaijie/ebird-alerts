function UpdateMeter(section) SKIN:Bang("!UpdateMeter", section) end
function ShowMeter(section) SKIN:Bang("!ShowMeter", section) end
function HideMeter(section) SKIN:Bang("!HideMeter", section) end
function UpdateMeterGroup(section) SKIN:Bang("!UpdateMeterGroup", section) end
function ShowMeterGroup(section) SKIN:Bang("!ShowMeterGroup", section) end
function HideMeterGroup(section) SKIN:Bang("!HideMeterGroup", section) end
function SetOption(section, option, assignment) SKIN:Bang("!SetOption", section, option, assignment) UpdateMeter(section) end
function GetVar(variable) return SKIN:GetVariable(variable) end
function SetVar(variable, assignment) SKIN:Bang("!SetVariable", variable, assignment) end
function Redraw() SKIN:Bang("!Redraw", "#CURRENTCONFIG#") end
function Write(section, variable, string, fileLocation) SKIN:Bang("!WriteKeyValue", section, variable, string, fileLocation) end
function WKV(variable, string, location)
    Write(location or "Variables", variable, string, "#@#Settings.inc")
    SetVar(variable, string)
end