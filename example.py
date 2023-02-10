from SpotiThief import SpotiThief

SPOTIFY_PLAYLIST_URL = "https://open.spotify.com/playlist/[PLAYLIST_ID]"

st = SpotiThief()
st.load_playlist_from_spotify(SPOTIFY_PLAYLIST_URL)
# st.load_playlist_from_file("playlist.json") # Or load from file
st.add_youtube_url_to_playlist()
st.save_playlist_to_file()
st.export_playlist_to_mp3()

# On next version I will add one SYNC function, that will do all the work for you 