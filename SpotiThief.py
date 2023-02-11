from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import json
import youtube_dl
import threading
from time import sleep
import os

DEFAULT_DOWNLOAD_PATH = "exported_playlist/"
DEFAULT_PLAYLIST_PATH = "playlist.json"

class SpotiThief:
    def __init__(self):
        self.song_list: list = []


    def sync(self, spotify_playlist_url: str = None, media_location: str = DEFAULT_DOWNLOAD_PATH):
        self.load_playlist_from_spotify(spotify_playlist_url=spotify_playlist_url, should_cache_playlist=False)
        self.add_youtube_url_to_playlist()
        self.__cache_playlist()

        songs_to_remove = self.get_songs_to_remove(media_location)
        self.__delete_songs(songs_to_remove, media_location)

        self.export_playlist_to_mp3()



    def load_playlist_from_spotify(self, spotify_playlist_url: str, should_cache_playlist: bool = True):
        MAX_LOOP_COUNT = 1000

        if spotify_playlist_url is None:
            print("No url provided")
            return

        print("Loading playlist from spotify url")

        driver = self.__get_driver_instance()
        driver.get(spotify_playlist_url)
        sleep(4)

        tracks = []
        last_track = None

        for _ in range(MAX_LOOP_COUNT):
            tracks = driver.find_elements(By.XPATH, '//*[@data-testid="tracklist-row"]')
            if last_track == tracks[-1]:
                break
            else:
                last_track = tracks[-1]

            self.__dom_to_json(tracks)
            driver.execute_script("arguments[0].scrollIntoView();", last_track)
            sleep(1)

        if should_cache_playlist:
            self.__cache_playlist()


    def save_cached_playlist_to_file(self, file_name: str = None):
        if self.song_list is None or file_name is None:
            print("No songs loaded or no file name provided")
            return
        
        print("Saving cached playlist to file")
        self.__cache_playlist(filename=file_name)

    
    def add_youtube_url_to_playlist(self):
        NUM_OF_DRIVERS_AND_THREADS = 5

        print ("Adding youtube urls to playlist")
        self.__import_youtube_urls_from_cache()

        drivers = []
        for i in range(NUM_OF_DRIVERS_AND_THREADS):
            drivers.append(self.__get_driver_instance())

        threads = []
        for i in range(len(self.song_list)):
            if self.song_list[i].get('youtube_url') is not None:
                continue
            
            thread = threading.Thread(target=self.__add_youtube_url_to_song, args=(i, drivers[i % NUM_OF_DRIVERS_AND_THREADS]))
            thread.start()
            threads.append(thread)

            if i % NUM_OF_DRIVERS_AND_THREADS == 0:
                for thread in threads:
                    thread.join()
                threads = []

        for thread in threads:
            thread.join()


    def export_playlist_to_mp3(self, location: str = DEFAULT_DOWNLOAD_PATH):
        MAX_THREADS = 15

        if self.song_list is None:
            print("No songs loaded")
            return

        print("Exporting playlist to mp3")

        threads = []
        for song in self.song_list:
            song_name = self.__get_full_song_name(song)

            if song.get('youtube_url') is None:
                print(f"Song {song['song_name']} has no youtube url")
                continue
            
            if os.path.isfile(f"{location}/{song_name}.mp3"):
                print(f"Song {song_name} already exists")
                continue

            if len(threads) >= MAX_THREADS:
                for thread in threads:
                    thread.join()
                threads = []

            thread = threading.Thread(target=self.__download_song, args=(song['youtube_url'], song_name, location))
            thread.start()
            threads.append(thread)
            sleep(2)

        for thread in threads:
            thread.join()


    def load_playlist_from_file(self, file_name: str):
        if file_name is None:
            print("No file name provided")
            return
        
        if not os.path.isfile(file_name):
            print("File does not exist")
            return
            
        print("Loading playlist from file")
        with open(file_name, "r", encoding="utf-8") as f:
            self.song_list = json.load(f)

    def get_songs_to_remove(self, location: str = DEFAULT_DOWNLOAD_PATH):
        if not os.path.isdir(location):
            return []

        songs_on_disk = []
        for song in os.listdir(location):
            songs_on_disk.append(song.split(".mp3")[0])

        songs_to_delete = []
        for song_on_disk in songs_on_disk:
            for song in self.song_list:
                if self.__get_full_song_name(song) == song_on_disk:
                    break
            else:
                songs_to_delete.append(song_on_disk + ".mp3")

        return songs_to_delete

    def get_new_songs(self, location: str = DEFAULT_DOWNLOAD_PATH):
        if not os.path.isdir(location):
            return []

        songs_on_disk = []
        for song in os.listdir(location):
            songs_on_disk.append(song.split(".mp3")[0])

        new_songs = []
        for song in self.song_list:
            for song_on_disk in songs_on_disk:
                if self.__get_full_song_name(song) == song_on_disk:
                    break
            else:
                new_songs.append(song)

        return new_songs

    ############ Private ############
    
    def __dom_to_json(self, element_list):
        for track in element_list:

            splitted_data = track.text.split("\n")
            if splitted_data[2] == "E" or splitted_data[2] == "Explicit":
                del splitted_data[2]

            if any(song['playlist_index'] == str(splitted_data[0]) for song in self.song_list):
                continue
                
            song_dict = {
                "playlist_index": str(splitted_data[0]),
                "song_name": self.__remove_special_characters(str(splitted_data[1])),
                "artist": self.__remove_special_characters(str(splitted_data[2])),
                "album": self.__remove_special_characters(str(splitted_data[3])),
                "release_date": str(splitted_data[4]),
                "duration": str(splitted_data[5]),
            }

            self.song_list.append(song_dict)

    def __get_youtube_url(self, driver, song, retries=0):
        if retries > 3:
            return None

        song_name = song['song_name']
        artist = song['artist']

        url = f"https://www.youtube.com/results?search_query={song_name}+{artist}"
        driver.get(url)
        sleep(2)

        a_tags = driver.find_elements(By.TAG_NAME, "a")
        youtube_url = None
        for a_tag in a_tags:
            if a_tag.get_attribute("href") is not None:
                if "watch" in a_tag.get_attribute("href"):
                    youtube_url = a_tag.get_attribute("href")
                    break

        if youtube_url is None or not youtube_url.startswith("https://www.youtube.com/watch?v="):
            youtube_url = self.__get_youtube_url(driver, song, retries + 1)

        return youtube_url

    def __download_song(self, video_url: str = None, song_name: str = None, location: str = None):
        if video_url is None or location is None:
            print("No url or location provided")
            return

        video_info = youtube_dl.YoutubeDL().extract_info(url = video_url,download=False)
        filename = song_name if song_name != None else f"{video_info['title']}.mp3"
        options={
            'format':'bestaudio/best',
            'keepvideo':False,
            'outtmpl': f'{location}/{filename}.mp3',
            'user-agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36',
        }

        with youtube_dl.YoutubeDL(options) as ydl:
            try:
                ydl.download([video_info['webpage_url']])

            except: # second chance, yes I know this is bad
                ydl.download([video_info['webpage_url']]) 

        print("Download complete... {}".format(filename))

    def __add_youtube_url_to_song(self, song_index: int, driver):
        if song_index >= len(self.song_list):
            print("Song index out of range")
            return

        if self.song_list[song_index].get('youtube_url') is not None:
            print("Song already has youtube url")
            return

        if driver is None:
            print("No driver provided")
            return

        url = self.__get_youtube_url(driver, self.song_list[song_index])
        self.song_list[song_index]['youtube_url'] = url

    def __remove_special_characters(self, string: str):
        special_characters = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for character in special_characters:
            string = string.replace(character, '')

        return string

    def __get_driver_instance(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument("--log-level=3")
        options.add_argument("--show-capture=no")

        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def __get_full_song_name(self, song):
        return song['song_name'] + " - " + song['artist']

    def __import_youtube_urls_from_cache(self):
        if not os.path.exists(DEFAULT_PLAYLIST_PATH):
            return

        old_playlist = []
        with open(DEFAULT_PLAYLIST_PATH, "r", encoding="utf-8") as f:
            old_playlist = json.load(f)

        for song in self.song_list:
            if song.get('youtube_url') is not None:
                continue

            for old_song in old_playlist:
                if old_song.get('youtube_url') is None:
                    continue

                if song['song_name'] == old_song['song_name'] and song['artist'] == old_song['artist']:
                    song['youtube_url'] = old_song['youtube_url']
                    break

    def __delete_songs(self, songs_to_delete: list = None, location: str = DEFAULT_DOWNLOAD_PATH):
        if songs_to_delete is None:
            print("No songs to delete")
            return

        print(f"Deleting {len(songs_to_delete)} songs")
        for song in songs_to_delete:
            print(f"Deleting song: {song}")
            os.remove(f"{location}/{song}")

    def __cache_playlist(self, filename: str = DEFAULT_PLAYLIST_PATH):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.song_list, f, indent=4, ensure_ascii=False)