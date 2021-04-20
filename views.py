from django.shortcuts import render
from django.urls import reverse
from django.conf import settings

from . import spotifyAPI
from . import spotify_auth_flow as saf
from .dashapps import vibe_compass_app

# Views
def generic_spotify_app(request):
    """ This view isn't used, but is a template for a Spotify App including Authorisation Flow
    The template was created for Vibe Compass """

    app_parameters = dict(
            client_id = "d86b3bf3bb2440b3be90feb5e1b9e4f6",
            client_secret = settings.SUNFIRE_CONFIG["VIBECOMPASS_SECRET"],
            redirect_uri = "https://sunfire.xyz/spotify/vibe-compass",
            session_entry = "vc_refresh_token",
            view_name = "vibe-compass",
        )
    session_entry = app_parameters["session_entry"] # the dictionary entry where we'll store this app's refresh_token

    # Pre-authenticated user
    if session_entry in request.session:
        try:
            client_creds = f"{app_parameters['client_id']}:{app_parameters['client_secret']}"
            sp = spotifyAPI.Client(client_creds, request.session[session_entry], refresh=True)
        except spotifyAPI.AccessRevoked:
            del request.session[session_entry] # delete invalid refresh token
            return render(request, "spotify/error.html", saf.spotify_error_context(0))
        request.session[session_entry] = sp.refresh_token # We reauthenticate in the constructor, so need to update the session token.
    # User has not authenticated before
    else:
        return saf.authentication_flow(request, app_parameters) # Takes user to next step of auth flow

    # Get list of user's playlists
    try:
        user_playlists = sp.get_users_playlists()
    except spotifyAPI.AccessRevoked:
        del request.session[session_entry]
        return render(request, "spotify/error.html", saf.spotify_error_context(0))
    except spotifyAPI.InvalidRequest:
        return render(request, "spotify/error.html", saf.spotify_error_context(4))
    request.session[session_entry] = sp.refresh_token # update session incase we had to refresh access tokens

    context = {"user_playlists": user_playlists}
    return render(request, "spotify/unused.html", context)


def vibe_compass(request):
    # Vibe Compass Parameters
    app_parameters = dict(
            client_id = "d86b3bf3bb2440b3be90feb5e1b9e4f6",
            client_secret = settings.SUNFIRE_CONFIG["VIBECOMPASS_SECRET"],
            redirect_uri = "https://sunfire.xyz/spotify/vibe-compass",
            session_entry = "vc_refresh_token",
            view_name = "vibe-compass",
        )
    session_entry = app_parameters["session_entry"] # the dictionary entry where we'll store this app's refresh_token

    # Pre-authenticated user
    dash_sess = request.session.get('django_plotly_dash', {}) # Django Dash only has access to request.session["django_plotly_dash"]
    if session_entry in dash_sess:
        try:
            client_creds = f"{app_parameters['client_id']}:{app_parameters['client_secret']}"
            sp = spotifyAPI.Client(client_creds, request.session["django_plotly_dash"][session_entry], refresh=True)
        except spotifyAPI.AccessRevoked:
            del request.session["django_plotly_dash"][session_entry] # delete invalid refresh token
            return render(request, "spotify/error.html", saf.spotify_error_context(0))
        request.session["django_plotly_dash"][session_entry] = sp.refresh_token # We reauthenticate in the constructor, so need to update the session token.
    # User has not authenticated before
    else:
        return saf.authentication_flow(request, app_parameters, dash_app=True) # Takes user to next step of auth flow

    return render(request, "spotify/vibecompass.html")

def vc_error(request):
    """ The vibe compass dash app redirects to this view on error """
    context = {
        "error_title": "Spotify Error",
        "error_description": ["There was an error with the Spotify API. Vibe Compass could not get access to your account. Reload to try again."],
        "button_href": reverse('vibe-compass')
        }
    return render(request, "spotify/error.html", context)

def logout(request):
    """ If things get messed up, give user a link to go to which can clear their session data
    They should be able to do a fresh login/authorisation flow """

    if "csrf_str" in request.session:
        del request.session["csrf_str"]

    if "vc_refresh_token" in request.session:
        del request.session["vc_refresh_token"]
    
    if "django_plotly_dash" in request.session:
        del request.session["django_plotly_dash"]
    
    return render(request, "spotify/error.html", {"error_title": "Logged out", "error_description":["Your session has been cleared and you have been logged out of Vibe Compass."], "button_href": reverse('vibe-compass')})
