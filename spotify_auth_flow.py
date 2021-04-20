from django.shortcuts import render, redirect
from django.urls import reverse

from . import spotifyAPI

import hashlib
from random import choice
from string import ascii_letters, digits

def authentication_flow(request, app_parameters, dash_app=False):
    """ Exepects request from Django, and parameters for a spotify App
    Returns the page to render for the next step of authentication """

    # Vibe Compass App
    client_id = app_parameters["client_id"]
    client_secret = app_parameters["client_secret"]
    client_creds = f"{client_id}:{client_secret}" # Combined
    redirect_uri = app_parameters["redirect_uri"]
    session_entry = app_parameters["session_entry"] # the dictionary entry in session to store token
    view_name = app_parameters["view_name"] # urls.py view name for redirection

    # Get query parameters passed from Spotify
    access_code = request.GET.get("code", None) # default None
    state = request.GET.get("state", None)
    if request.GET.get("error", False) == "access_denied":
        return render(request, "spotify/error.html", spotify_error_context(2))
    
    # User needs to be redirected to Spotify to grant permissions
    if access_code == None:
        #print("User being redirected to Spotify")
        # CSRF Prevention
        csrf_str = "".join(choice(ascii_letters+digits) for _ in range(12)) # generate random 12 digit alphanumeric
        request.session["csrf_str"] = csrf_str # save to user's session data
        csrf_tok = sha256_encrypt(csrf_str)

        scope="user-modify-playback-state%20playlist-read-private%20playlist-read-collaborative" # permissions to queue songs, read playlists
        spotify_auth_url = f"https://accounts.spotify.com/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&scope={scope}&state={csrf_tok}"
        return redirect(spotify_auth_url)
    else: # User has agreed and been redirected from spotify
        #print("User has come from Spotify")
        if "csrf_str" in request.session:
            csrf_str = request.session["csrf_str"]
            csrf_tok = sha256_encrypt(csrf_str)
        else: # If user has no csfr_str, then they have query url but didn't come from here or have disabled cookies
            #print("User has no CSRF token!")
            return render(request, "spotify/error.html", spotify_error_context(1))

        if state != csrf_tok:
            #print("Invalid CSRF Token")
            #print(f"Got {state=}, expected {csrf_tok=}")
            return redirect(view_name)
        else: # CSRF is valid
            # Authenticate user to get Access Token
            try:
                sp = spotifyAPI.Client(client_creds, access_code) # Create Spotify Class (this also exchanges code for tokens)
            except spotifyAPI.InvalidAuthorisation:
                return render(request, "spotify/error.html", spotify_error_context(3))
            
            # Save authentication details to session for future authentication
            if dash_app == False:
                request.session[session_entry] = sp.refresh_token 
            else:
                request.session["django_plotly_dash"] = {session_entry: sp.refresh_token}
            
            return redirect(view_name) 

def sha256_encrypt(password):
    """ Hash a string with sha256 encryption """
    sha = hashlib.sha256()
    sha.update(password.encode()) # hash csrf string
    return sha.hexdigest()

def spotify_error_context(id):
    """ A list of errors and messages to return to the user in the case of handled errors """
    error_context = [
        # 0 Access Revoked
        {
            "error_title": "Error - Access Revoked",
            "error_description": ["It appears you have revoked access, preventing Vibe Compass from accessing your Spotify Account.", "Click below to be redirected to Spotify if you'd like to grant access again."],
            "button_href": reverse('vibe-compass')
        },
        # 1 Missing CSRF Token
        {
            "error_title": "Error - Missing Authentication Token",
            "error_description": ["I was expecting you to have a cookie with an authentication token, but couldn't find one. If this is your first visit here then don't worry, just click below to refresh",
                                "If you're seeing this error after granting access to Vibe Compass, something went wrong. If you have disabled cookie, you may need to enable them. Cookies are used only for security purposes."],
            "button_href": reverse('vibe-compass')
        },
        # 2 User rejected access
        {
            "error_title": ":( You rejected access",
            "error_description": ["You chose not to grant permission for Vibe Compass to access your Spotify account.",
                                "If you change your mind, hit reload below."],
            "button_href": reverse('vibe-compass')
        },
        # 3 Invalid Authorsation
        {
            "error_title": "Error - Invalid Authorisation",
            "error_description": ["Vibe Compass was not properly authorised to access your Spotify account. Hit reload to try again."],
            "button_href": reverse('vibe-compass')
        },
        # 4 Generic Invalid Request
        {
            "error_title": "Error - Bad Request",
            "error_description": ["A bad request was made to the Spotify API. I'm not sure why. Sorry."],
            "button_href": reverse('vibe-compass')
        },
    ]
    return error_context[id]
