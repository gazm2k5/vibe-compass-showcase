import requests
from datetime import datetime, timedelta
import base64

class Client(object):
    def __init__(self, client_creds, accref_code, refresh=False):
        self.client_creds = client_creds
        if refresh == False: # First time authentication
            self.authenticate(accref_code)
        else: # Refresh authentication
            self.refresh_token = accref_code
            self.authenticate(accref_code, refresh=True)
        self.user_playlists = []

    @property
    def default_json_header(self):
        return {
                'Accept':'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
                }

    def authenticate(self, accref_code, refresh=False):
        """ Expects an access_code or refresh_token
        Updates class access_token, refresh_token and expiry
        Returns True if successful, else False """
        url = "https://accounts.spotify.com/api/token"
        token_payload = {
            "grant_type":"authorization_code" if not refresh else "refresh_token",
            "code" if not refresh else "refresh_token" : accref_code,
            "redirect_uri": "https://sunfire.xyz/spotify/vibe-compass", # there is no redirect, used for validation only
        }

        # Encode client credentials as base64 for added security
        client_creds_b64 = base64.b64encode(self.client_creds.encode())
        token_headers = {
            "Authorization": f"Basic {client_creds_b64.decode()}",
            'Content-Type':"application/x-www-form-urlencoded",
        }

        # Make Request
        r = requests.post(url, headers=token_headers, params=token_payload)
        if self.status_code_check(r):
            expiry = datetime.now() + timedelta(seconds=r.json()["expires_in"])
            self.access_token = r.json()["access_token"]
            self.expiry = expiry
            if "refresh_token" in r.json(): # if we're refreshing, we won't get a refresh token
                self.refresh_token = r.json()["refresh_token"]
            return True
        else:
            return False

    def reauthenticate(fn):
        """ Decorator function to ensure access/refresh tokens are fresh
        for any API call that requires authentication """
        def wrapper(*args, **kwargs):
            self = args[0]
            if datetime.now() >= self.expiry: # Reauthentication required
                self.authenticate(self.refresh_token, refresh=True)
            result = fn(*args, **kwargs)
            return result
        return wrapper
        
    @reauthenticate
    def get_track(self, trackid):
        """ Expects a single track ID or a list of track IDs and returns audio parameters as json """
        if type(trackid) == list:
            requeststring = ",".join(trackid) # convert list to string separated by commas
        elif type(trackid) == str:
            requeststring = trackid
            
        url = f"https://api.spotify.com/v1/tracks/{requeststring}"
        r = requests.get(url, headers=self.default_json_header)
        if self.status_code_check(r):
            return r.json()

    @reauthenticate            
    def get_playlist(self, playlistid, market="from_token"):
        """ Gets tracks from a playlist from its URI """
        url = f"https://api.spotify.com/v1/playlists/{playlistid}/tracks?market={market}"
        r = requests.get(url, headers=self.default_json_header)
        if self.status_code_check(r):
            return r.json()

    @reauthenticate
    def get_users_playlists(self):
        """ Gets a list of all the users public and private playlists """
        url = "https://api.spotify.com/v1/me/playlists?limit=50"

        r = requests.get(url, headers=self.default_json_header)
        if self.status_code_check(r):
            self.user_playlists = []
            [ self.user_playlists.append({"name": item["name"], "id" : item["id"]}) for item in r.json()["items"] ]
        return self.user_playlists
    
    @reauthenticate
    def queue_song(self, trackid):
        url = f"https://api.spotify.com/v1/me/player/queue?uri=spotify:track:{trackid}"
        r = requests.post(
            url,
            headers={'Authorization': f'Bearer {self.access_token}'}
        )
        self.status_code_check(r) # we don't get json from a post request so can't do this
        return r
    
    @reauthenticate
    def get_parameters(self, trackids):
        """ Expects a single track ID or a list of track IDs and returns audio parameters as json """
        if type(trackids) == list:
            requeststring = ",".join(trackids) # convert list to string separated by commas
        elif type(trackids) == str:
            requeststring = trackids
        url = f"https://api.spotify.com/v1/audio-features?ids={requeststring}"
        r = requests.get(url, headers=self.default_json_header)
        if self.status_code_check(r):
            return r.json()

    @staticmethod
    def status_code_check(response):
        status_code = response.status_code
        if status_code in range(200,299):
            return True
        else:
            response_json = response.json() # post requests do not have responses if successful, so have to do this here

            # First we must parse the error as the JSON is not consistent
            if "error_description" in response_json:
                error_msg = response_json["error_description"]
            elif "error" in response_json:
                error_msg = response_json["error"]["message"]
            else:
                # Fallback if the above formats aren't correct
                print(response_json)
                raise InvalidRequest(status_code, f"Unexpected JSON format. JSON printed above.")

            if error_msg == "Refresh token revoked":
                raise AccessRevoked(status_code, error_msg)
            elif error_msg == "Invalid authorization code":
                raise InvalidAuthorisation(status_code, error_msg)
            elif error_msg == "Player command failed: No active device found":
                raise NoDevice(status_code, error_msg)
            else:
                # Any generic errors
                raise InvalidRequest(status_code, error_msg)

# Custom Exceptions
class InvalidRequest(Exception):
    """ Raise exception if an API call does not result in a successful response """

    def __init__(self, status_code, error_description):
        self.status_code = status_code
        self.error_description = error_description
        super().__init__(f"Invalid Request in Spotify API =>\n\tStatus Code {status_code}\n\tError Description: {error_description}")

class AccessRevoked(InvalidRequest):
    """ Specific Exception if user revokes access to the app """
    pass

class InvalidAuthorisation(InvalidRequest):
    """ Specific Exception if user revokes access to the app """
    pass
    
class NoDevice(InvalidRequest):
    """ Specific Exception if no active device is found """
    pass
