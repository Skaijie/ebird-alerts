[Variables]
    ; --- CONFIGURATION ---
    ; Define up to 5 regions.
    Region1=SG
    Region2=
    Region3=
    Region4=
    Region5=
    internalCurrentTab=SG
    ; --- Species settings ---
    ; Input lifers manually in addition to eBird life list?
    ;SettingAddManualLifers=1
    ; Use global lifelist when showing needs?
    SettingUseGlobalLifeList=1
    ; Show subspecies separately?
    SettingSubspeciesDifferentiation=0
    ; Only show rare sightings if they are confirmed?
    SettingHideUnconfirmedSightings=0
    ; --- Alert frequency ---
    ; The widget will show alerts dating back to this many days ago
    SettingMaxDays=7
    ; Run the script automatically on intervals? (Including on widget refresh)
    SettingAutoRefresh=1
    ; Reduce refresh rate at night?
    SettingReduceRefreshNight=1
    ; Normal (day) refresh rate
    SettingNormalRefreshRate=15
    ; Night refresh rate
    SettingNightRefreshRate=90
    ; --- Advanced ---
    ; Enter debug mode (shows more logs and prevents Python script from running every time the widget is refreshed)
    SettingDebug=1
    ; Data will be called from file (previously obtained data) instead of APIs
    SettingOfflineMode=0
    ; Self-explanatory
    SettingDarkMode=1

    ; General variables
    fontNameDefault=Lexend
    fontSizeDefault=(10*(#SCREENAREAHEIGHT#/1080))
    fontSizeHalf=(#fontSizeDefault#*0.5)
    fontColorFront=224,224,224,224
    fontColorBack=32,32,32,224
    fontColorShade=192,192,192
    fontColorShade2=96,96,96,0
    fontColorGreen=115,190,132,255
    fontColorRed=225,54,75,255
    fontColorLink=0,102,255,255
    fontColorRare=49,111,230,255
    fontColorNR=127,177,255,255
    fontColorNeed=69,133,254,255
    MaxScrollIndex=30
    ScrollStep=10
    HoldState=0
SettingAddDelSpecies=Mangrove Whistler
