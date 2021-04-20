import numpy as np
import pandas as pd
import plotly.graph_objs as go

def distance_to_all(df, coord1):
    """ Expects coordinates in multi dimensional space
    Returns euclidean distance between coord1 and songs in df """
    all_songs = df.loc[:,"danceability":"valence"].to_numpy(dtype=np.float64)
    #return np.sqrt(np.sum(np.square(this_song - all_songs), axis=1))
    return np.linalg.norm(coord1 - all_songs, axis=1) # euclidean distance

# TODO: Radius should be based on density so we don't go back on ourselves, or even directional.

def song_radius(df, coord1, radius=0.15):
    """ Expects index for a song and radius
    Returns a list of indexes of all other songs within that radius """
    distances = distance_to_all(df, coord1)
    nearby_songs = np.where(distances <= radius)[0] # np.where returns a tuple(?) of arrays
    # nearby_songs = np.delete(nearby_songs, np.where(nearby_songs == idx1)) # remove this song from list of nearby songs
    return nearby_songs

def uri_to_idx(df, *args):
    """ Expects spotify uris and a dataframe
    Returns dataframe index for those spotify URIs """
    idxs = []
    for uri in args:
        idxs.append(df[df["spotify_id"] == uri].index[0])
    return idxs

def get_direct_path(df, origin, destination, steps):
    """ Expects a start point/end point indexes, and the number of steps to get to the end 
    Returns an array of all the points inbetween """

    # Get coordinates of origin and destination, and step vector
    origin_coords = df.loc[origin, "danceability":"valence"].to_numpy(dtype=np.float64)
    destination_coords = df.loc[destination, "danceability":"valence"].to_numpy(dtype=np.float64)
    step = (destination_coords - origin_coords)/steps # step = full route / steps

    path_coords = np.zeros((steps+1, origin_coords.shape[0])) # Set up empty array
    for n in range(0, steps+1):
        path_coords[n, :] = origin_coords + n*step

    return path_coords
        
def plot_bearing(df, origin_uri, destination_uri, steps):
    """ Expects datamfrae, index of origin and destination, and number of steps desired between them 
    Plots a graph of the route to take, and returns the indexes of the points (songs) """
    
    # Convert URI to indexes
    origin, destination = uri_to_idx(df, origin_uri, destination_uri)
    
    # Get straight line path
    stops = get_direct_path(df, origin, destination, steps)
    
    # Find a route
    playlist = [origin] # playlist will be a list of indexes, which we can use with the main df, ie. df[playlist]
    #playlist_combinations = [[origin]]  # not currently used
    for stop in stops[1:-1]: # first and last stops are origin/destination
        song_choices = song_radius(df, stop) # get options for next song
        # playlist_combinations.append(song_choices)
        
        # remove duplicates and add next song
        set_a = set(playlist + [destination])
        set_b = set(song_choices)
        song_choices = list(set_b - set_a) # remove any duplicates
        if len(song_choices) > 0:
            next_song = np.random.choice(song_choices)
            playlist.append(next_song)
            
    playlist.append(destination)
    playlist = [int(num) for num in playlist] # convert int64 to regular ints

    return stops, playlist
