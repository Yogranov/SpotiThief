from SpotiThief import SpotiThief

st = SpotiThief()
url = input("Enter Spotify playlist URL: ")
alternative_media_folder = input("Enter alternative media folder (leave empty for default): ")

if alternative_media_folder != "":
    st.sync(url, alternative_media_folder)
else:
    st.sync(url)