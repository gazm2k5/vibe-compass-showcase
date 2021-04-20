from django.conf import settings
from django.urls import reverse

import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go
from django_plotly_dash import DjangoDash
from dash.exceptions import PreventUpdate

from . import vc_linalg # linear algebra for plotting routes

import json
import numpy as np
import pandas as pd

from .. import spotifyAPI

app = DjangoDash("vibe-compass-dash") # replaces dash.Dash

# Vibe Compass Parameters
app_parameters = dict(
        client_id = "d86b3bf3bb2440b3be90feb5e1b9e4f6",
        client_secret = settings.SUNFIRE_CONFIG["VIBECOMPASS_SECRET"],
        redirect_uri = "https://sunfire.xyz/spotify/vibe-compass",
        session_entry = "vc_refresh_token",
        view_name = "vibe-compass",
    )
session_entry = app_parameters["session_entry"] # the dictionary entry where we'll store this app's refresh_token
client_creds = f"{app_parameters['client_id']}:{app_parameters['client_secret']}"

# App layout/HTML
def serve_layout():
    """ Returns Dash App layout to be served on page load """
    return html.Div([
        # Main Container
        html.Div([
            # Controls Panel (left)
            html.Div([
                html.H2("Your Spotify Playlists"),
                html.Div([
                    dcc.Dropdown(id="playlist-selector"),
                    html.Button("Refresh", id="refresh-playlists", n_clicks=0, className="floatright btn btn-primary"),
                ], className="options1"),
                html.Div([                   
                    html.H2("Origin"),
                    dcc.Dropdown(id="origin-song"),
                    html.H2("Destination"),
                    dcc.Dropdown(id="destination-song"),
                    html.H2("Steps"),
                    dcc.Input(id="steps", type="number", value=5, min=1, max=50),
                    html.Button("Plot Route", id="plot-route", n_clicks=0, className="floatright btn btn-primary"),
                ], className="options2"),
            ], className="panel"),

            # Playlist panel (right)
            html.Div([
                html.H2("Your Route"),
                html.Div(id="playlist-display"), # display the route
                html.Button("Add to Queue", id="queue-playlist", disabled=True, n_clicks=0, className="floatright btn btn-primary"),
            ], className="panel")

        ], className="app-container"),
                
        dcc.Store(id='dataframe-json'), # main dataframe of playlist. default storage_type="memory"
        dcc.Store(id="route-json"), # serialised route playlist
        dcc.Store(id="playlist-songs"), # dict of name: song, value: id, for dropdown lists
        # dcc.Store(id='sp-client', storage_type="memory"), # TODO: Serialize spotify class
        html.Div([
            html.H2("Vibe Map", style={"text-align": "center"}),
            dcc.Graph(id="graph", figure={"data":[], "layout":layout}),
        ], className="panel"),
    
        html.Div(id="queued-modal", className="hidden"), # modal

        html.Div(id="redirect-div", style={"visibility":"hidden"}), # This div used for redirecting in the event of an error

    ])

# Graph layout
layout = go.Layout(
        height=750, # let width scale to html
        scene = dict(
            xaxis=dict(title='Danceability', showgrid=True, gridcolor='#b3b3b3'),
            yaxis=dict(title='Energy', showgrid=True, gridcolor='#b3b3b3'),
            zaxis=dict(title='Valence', showgrid=True, gridcolor='#b3b3b3'),
            bgcolor="#181818", # 3dScatter background colour
            ),
        plot_bgcolor='#181818', # I think this is only for 2D scatter
        font=dict(
            family="Lato, sans-serif",
            size=12,
            color="#b3b3b3",
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=30, r=15, l=15, b=15),
        showlegend=False,)

app.layout = serve_layout

# Callbacks

# On page load and button press, get users playlists and populate dropdown
@app.expanded_callback(
    dash.dependencies.Output("playlist-selector", 'options'),
    [dash.dependencies.Input('refresh-playlists', 'n_clicks'),]
)
def page_load(n_clicks, session_state=None, **kwargs):

    if session_state is None:
        raise NotImplementedError("Cannot handle a missing session state")
    refresh_token = session_state.get(session_entry, None)
    sp = spotifyAPI.Client(client_creds, refresh_token, refresh=True)

    # Get list of user's playlists
    try:
        user_playlists = sp.get_users_playlists()
    except spotifyAPI.AccessRevoked:
        if session_entry in session_state:
            del session_state[session_entry]
        return [ {"label":"error", "value":"vc_error"} ]
    except spotifyAPI.InvalidRequest:
        return [ {"label":"error", "value":"vc_error"} ]

    playlist_dropdown = [ {"label":item["name"], "value": item["id"] } for item in user_playlists ]
    return playlist_dropdown

# When playlist item is selected, save track data as json
@app.expanded_callback(
    dash.dependencies.Output("dataframe-json", "data"),
    [dash.dependencies.Input("playlist-selector", "value")]
)
def load_playlist_data(playlist_uri, session_state=None, **kwargs):
    if playlist_uri == None:
        return None
    if session_state is None:
        raise NotImplementedError("Cannot handle a missing session state")
    refresh_token = session_state.get(session_entry, None)
    sp = spotifyAPI.Client(client_creds, refresh_token, refresh=True)
    
    # Get a JSON for playlist's tracks
    rjson = sp.get_playlist(playlist_uri)

    # Create Dictionary for track details
    data = {"artist":[], "track_title":[], "album_art_url":[], "spotify_id":[]}
    for item in rjson["items"]:
        data["artist"].append(item["track"]["artists"][0]["name"])
        data["track_title"].append(item["track"]["name"])
        data["album_art_url"].append(item["track"]["album"]["images"][2]["url"]) # 0 for 640, 1 for 300, 2 for 64
        data["spotify_id"].append(item["track"]["id"])

    # Also get Track parameters
    data["danceability"] = []
    data["energy"] = []
    data["valence"] = []

    rjson2 = sp.get_parameters(data["spotify_id"])

    for item in rjson2["audio_features"]:
        data["energy"].append(item["energy"])
        data["valence"].append(item["valence"])
        data["danceability"].append(item["danceability"])

    return json.dumps(data)

# Convert full df json to dict; song artist/title and uri
@app.callback(
    dash.dependencies.Output("playlist-songs", "data"),
    [dash.dependencies.Input("dataframe-json", "data")]
)
def update_song_list(main_df_str, **kwargs):

    if main_df_str == None:
        # raise PreventUpdate
        return None

     # Create dataframe from dictionary
    json_data = json.loads(main_df_str)
    if len(json_data) == 0: # no data
        print("Ruentint none")
        return None

    # playlist_dropdown = [ {"label":item["name"], "value": item["id"] } for item in user_playlists ]
    song_dropdown = []
    for i in range(len(json_data["artist"])):
        song_dropdown.append(
            {"label": f"{json_data['artist'][i]} - {json_data['track_title'][i]}",
            "value": json_data['spotify_id'][i] }
        )
    return song_dropdown

# Update 2 song drop downs with playlist songs
@app.callback(
    dash.dependencies.Output("origin-song", "options"),
    [dash.dependencies.Input("playlist-songs", "data")]
)
def update_songs_dropdowns(songs, **kwargs):
    if type(songs) == type(None):
        return ""
    return songs

@app.callback(
    dash.dependencies.Output("destination-song", "options"),
    [dash.dependencies.Input("playlist-songs", "data")]
)
def update_songs_dropdowns(songs, **kwargs):
    if type(songs) == type(None):
        return ""
    return songs

# When song dropdowns are updated, clear their value
@app.callback(
    dash.dependencies.Output("origin-song", "value"),
    [dash.dependencies.Input("origin-song", "options")]
)
def update_songs_dropdowns(songs, **kwargs):
    return None

@app.callback(
    dash.dependencies.Output("destination-song", "value"),
    [dash.dependencies.Input("destination-song", "options")]
)
def update_songs_dropdowns(songs, **kwargs):
    return None

# Plot the main dataframe to the graph
def plot_master_df(df):
    """ Expects a playlist as a dataframe and returns the plotly objects """
    # Plot Graph
    plot_data_tracks = go.Scatter3d(
        x=df["danceability"], y=df["energy"], z=df["valence"],
        text=df['artist'] + " - " + df['track_title'],
        hovertemplate =
            '<b>%{text}</b><br>' +
            'danceability: %{x}<br>'+
            'energy: %{y}<br>' +
            'valence: %{z}' +
            '<extra></extra>',
        mode="markers",
        marker=dict(
            size=6,
            color=df["energy"],
            colorscale='Viridis',
            opacity=0.8
        )
    )

    return plot_data_tracks

def plot_route(route_df):
    """ expects df[playlist] and returns plotly objects  """
    return go.Scatter3d(x=route_df["danceability"], y=route_df["energy"], z=route_df["valence"],
                     mode="lines",
                     hoverinfo='skip',
                     line=dict(
                            color='white',
                            width=3
                       )
                    )

def plot_direct(stops):
    """ Expects stops as numpy array, ie. the direct line from A to B """
    stops = np.array(stops) # convert from list to np array
    return go.Scatter3d(x=stops[:,0], y=stops[:,1], z=stops[:,2],
                     mode="lines+markers",
                     hoverinfo='skip',
                     marker=dict(
                         #symbol="x",
                         size=4,
                         opacity=0.5
                     ),
                     line=dict(
                         color='rgba(255, 80, 80, 0.6)',
                         width=3,
                       )
                    )

# Update main Graph
@app.callback(
    dash.dependencies.Output("graph", "figure"),
    [dash.dependencies.Input("dataframe-json", "data"), # Input: Dataframe, or Plot Route button > route json
    dash.dependencies.Input("route-json", "data")]
)
def plot_playlist_data(main_df_str, route_str, **kwargs):

    # Find out which input triggered the change
    ctx = dash.callback_context
    if ctx.triggered[0]["prop_id"] == "dataframe-json.data": # if we have picked a new playlist
        route_str = None # clear the route

    # Create dataframe from dictionary]
    if main_df_str == None:
        raise PreventUpdate
    main_df_json = json.loads(main_df_str)
    if len(main_df_json) == 0: # no data
        raise PreventUpdate
    df = pd.DataFrame(main_df_json)

    # Get plotly object for main df
    plot_data_tracks = plot_master_df(df)

    # Load any routes may have been passed in
    if type(route_str) == type(None):
        return { "data":[plot_data_tracks], "layout":layout }
    else:
        route_json = json.loads(route_str)
        stops = route_json["stops"]
        playlist = route_json["route"]

        # Plot other lines
        plot_direct_route = plot_direct(stops)
        plot_playlist_route = plot_route(df.iloc[playlist])
        return { "data":[plot_data_tracks, plot_direct_route, plot_playlist_route], "layout":layout }


# Get Route to plot
@app.callback(
    dash.dependencies.Output("route-json", "data"),
    [dash.dependencies.Input("plot-route", "n_clicks"), # Input: Plot Route Button
    dash.dependencies.Input('playlist-selector', 'value')], # Input: change of playlist
    [dash.dependencies.State("origin-song", "value"),
    dash.dependencies.State("destination-song", "value"),
    dash.dependencies.State("steps", "value"),
    dash.dependencies.State("dataframe-json", "data")]
)
def get_stops(n_clicks, refresh, origin_uri, destination_uri, steps, json_data, **kwargs):
    
    # Do not update on page load
    if n_clicks == 0 or origin_uri == None or destination_uri == None:
        raise PreventUpdate

    # Find out which input triggered the change
    ctx = dash.callback_context
    if ctx.triggered[0]["prop_id"] == "playlist-selector.value": # if we have picked a new playlist
        return None # Clear json

    # Create dataframe from dictionary
    data = json.loads(json_data)
    if len(data) == 0: # no data
        raise PreventUpdate
    df = pd.DataFrame(data)
    
    # Get direct path as np array coordinates stops, and playlist route as list of indexes for main df
    stops, route = vc_linalg.plot_bearing(df, origin_uri, destination_uri, steps)
    stops = stops.tolist() # we want to serialise so cannot remain as numpy array

    route_data = {"stops": stops, "route": route}
    return json.dumps(route_data)

# Once route is generated, display in div
@app.callback(
    dash.dependencies.Output("playlist-display", "children"),
    [dash.dependencies.Input("route-json", "data")], # Input: Route Data update
    [dash.dependencies.State("dataframe-json", "data")], 
)
def display_route(route_str, main_df_str, **kwargs):

    if type(route_str) == type(None):
        return html.Ul(id="generated-route", children=None)

    # Create dataframe from dictionary
    main_df_json = json.loads(main_df_str)
    if len(main_df_json) == 0: # no data
        raise PreventUpdate
    df = pd.DataFrame(main_df_json)

    route_json = json.loads(route_str)
    playlist = route_json["route"]
    route_df = df.iloc[playlist]

    route_songs = []
    for row in route_df.iterrows():
        my_str = f"{row[1]['artist']} - {row[1]['track_title']}"
        img = html.Img(src=row[1]['album_art_url'], height="32")
        # ele = html.Span([img, html.Li(my_str)])
        ele = html.Li([img, my_str])
        route_songs.append(ele)

    return html.Ul(id="generated-route", children=route_songs)

# Enable/Disable queue button
@app.callback(
    dash.dependencies.Output("queue-playlist", "disabled"),
    [dash.dependencies.Input("queued-modal", "children"), # Input: queue playlists button
    dash.dependencies.Input("route-json", "data")], # Input: Route Data update 
)
def toggle_queue_button(queued_modal, route_str, **kwargs):
    ctx = dash.callback_context
    
    # Big nested if to check if modal is result of an error (no spotify device)
    if type(queued_modal) != type(None):
        if "props" in queued_modal:
            if "className" in queued_modal["props"]:
                if queued_modal["props"]["className"] == "modal-error":
                    raise PreventUpdate

    if ctx.triggered[0]["prop_id"] == "route-json.data": # if we have generated a new route
        if route_str == None:
            return True
        else:
            return False
    elif ctx.triggered[0]["prop_id"] == "queued-modal.children": # if we queue songs
        return True # disable the button to prevent it being double clicked

# Change queue button text
@app.callback(
    dash.dependencies.Output("queue-playlist", "children"),
    #[dash.dependencies.Input("queue-playlist", "n_clicks"), # Input: queue playlists button
    # Because we need the modal to update to check for errors, we use modal as input and not button
    [dash.dependencies.Input("queued-modal", 'children'),
    dash.dependencies.Input("route-json", "data")], # Input: Route Data update 
    #[dash.dependencies.State("queued-modal", 'children')]
)
def change_queue_text(queued_modal, route_str, **kwargs):
    ctx = dash.callback_context

    # Big nested if to check if modal is result of an error (no spotify device)
    if type(queued_modal) != type(None):
        if "props" in queued_modal:
            if "className" in queued_modal["props"]:
                if queued_modal["props"]["className"] == "modal-error":
                    raise PreventUpdate

    if ctx.triggered[0]["prop_id"] == "route-json.data": # if we have generated a new route
        return "Add to Queue"
    elif ctx.triggered[0]["prop_id"] == "queued-modal.children": # if we queue songs
        return "Queued ✔️"

# Queue songs
@app.expanded_callback(
    dash.dependencies.Output("queued-modal", 'children'),
    [dash.dependencies.Input("queue-playlist", "n_clicks")], # Input: Queue Songs Button 
    [dash.dependencies.State("dataframe-json", "data"),
    dash.dependencies.State("route-json", "data")]
)
def queue_songs(n_clicks, main_df_str, route_str, session_state=None, **kwargs):

    if session_state is None:
        raise NotImplementedError("Cannot handle a missing session state")
    refresh_token = session_state.get(session_entry, None)
    sp = spotifyAPI.Client(client_creds, refresh_token, refresh=True)

    if type(route_str) == type(None): # empty json
        raise PreventUpdate

    if n_clicks == 0:
        raise PreventUpdate

    # Queue songs
    route_json = json.loads(route_str)

    # Create dataframe from dictionary
    main_df_json = json.loads(main_df_str)
    df = pd.DataFrame(main_df_json)

    playlist = route_json["route"]
    route_df = df.iloc[playlist]
    
    songs_queued = [html.B(html.Li("Queued songs:"))]

    # We generate a random number as the id, as the js frontend is looking for a change in DOM
    # It unfortunately does not see changes in the li elements, only in the immediate child (Ul)
    from random import choice
    num = str(choice(range(1,1000000)))
    id = f"random-{num}"
    
    for row in route_df.iterrows():
        artist = row[1]["artist"]
        track_title = row[1]["track_title"]
        track_id = row[1]["spotify_id"]
        try:
            sp.queue_song(track_id)
        except spotifyAPI.AccessRevoked:
            if session_entry in session_state:
                del session_state[session_entry]
            return dcc.Location(pathname=reverse("vc-error-generic"), id="foo")
        except spotifyAPI.NoDevice:
            return html.Div("Could not find an active device! Please launch Spotify and try starting a song.", className="modal-error", id=id)
        except spotifyAPI.InvalidRequest:
            return dcc.Location(pathname=reverse("vc-error-generic"), id="foo")
        
        songs_queued.append(html.Li(f"{artist} - {track_title}"))
   
    return html.Ul(songs_queued, id=id)

# Error handling
# Redirects to error page on Spotify API failure
@app.callback(
    dash.dependencies.Output("redirect-div", 'children'),
    [dash.dependencies.Input("playlist-selector", 'options')],
)
def redirecter(options, **kwargs):
    if len(options) > 0:
        if options[0]["label"] == "error" and options[0]["value"] == "vc_error":
            return dcc.Location(pathname=reverse("vc-error"), id="foo")
