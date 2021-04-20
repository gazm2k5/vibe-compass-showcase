# vibe-compass-showcase
The Vibe Compass app is featured on my website, https://www.sunfire.xyz/spotify/vibe-compass

It is a concept for a method of creating dynamics playlists by having the user create a large playlist with all their desired songs, and using the app to generate an order to pursue the vibe you want, rather than queuing songs manually.

This github repo is a showcase, as the actual implementation of the app is part of my Django implementation of the entire website and is therefore private. This public repo serves to show how the app was implemented.

# How the app works
The views.py file first tells Django which page to render, utilising the Spotify Authorisation flow implemented in spotify_auth_flow.py. Upon successful Authorisation, the user is directed to the Dash app, vibe_compass_app.py.
This app makes numerous requests to Spotify using the SpotifyAPI.py which I wrote, to get access to the users spotify data including playlists, and allows the user to queue their dynamically generated playlist.

It should be noted that this app is simply a concept, with the major hurdle being generating a more useful set of parameters, as by default Spotify only offers a handful which are not always accurate. That is, it may label a song as 90/100 on Danceability when in reality it's a very slow song.
