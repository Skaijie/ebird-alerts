# ebird-alerts
(readme WIP)

A Rainmeter widget to show eBird rare/needs alerts.

# Setup
(This is not meant for download yet)

This widget minimally requires an eBird API key to function. You can obtain your API key from the eBird website. Do not share this key with anyone.  
Once you have your key, install the widget and input your API key.

# Usage and legend
**\[N\]:** Your target (lifer) birds  
**\[R\]:** Birds that are rare for the selected region and date

For rare sightings, confirmed sightings have the location text in white, while unconfirmed sightings are grey.  
Sightings that are not considered rare are always grey, since eBird does not review these for confirmation.

# Settings
...

# Known issues/to-do
* Observations removed from the eBird database are not synced (can be fixed easier now that rare definition follows eBird's)
* Some lifers are not registered as such (?)
* Goofy repetition in sighting.del_sighting_multi()
* Widget does not update the "Refreshing alerts" text
* ...
