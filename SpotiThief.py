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


    def load_playlist_from_spotify(self, spotify_playlist_url: str, save_to_file: bool = False, file_name: str = None):
        if spotify_playlist_url is None:
            print("No url provided")
            return

        driver = self.__get_driver_instance()
        driver.get(spotify_playlist_url)
        sleep(4)

        tracks = []
        last_track = None
        while True:
            tracks = driver.find_elements(By.XPATH, '//*[@data-testid="tracklist-row"]')
            if last_track == tracks[-1]:
                break
            else:
                last_track = tracks[-1]

            self.__dom_to_json(tracks)
            driver.execute_script("arguments[0].scrollIntoView();", last_track)
            sleep(1)

        if save_to_file:
            if file_name == None:
                file_name = DEFAULT_PLAYLIST_PATH

            with open(file_name, "w", encoding="utf-8") as f:
                json.dump(self.song_list, f, indent=4, ensure_ascii=False)


    def save_playlist_to_file(self, file_name: str = None):
        if self.song_list is None:
            print("No songs loaded")
            return
        
        if file_name is None:
            file_name = DEFAULT_PLAYLIST_PATH

        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(self.song_list, f, indent=4, ensure_ascii=False)

    
    def add_youtube_url_to_playlist(self):
        NUM_OF_DRIVERS_AND_THREADS = 5

        drivers = []
        for i in range(NUM_OF_DRIVERS_AND_THREADS):
            drivers.append(self.__get_driver_instance())

        threads = []
        for i in range(len(self.song_list)):
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
        MAX_THREADS = 100

        if self.song_list is None:
            print("No songs loaded")
            return

        threads = []
        for song in self.song_list:
            if song.get('youtube_url') is None:
                print(f"Song {song['song_name']} has no youtube url")
                continue
            
            if len(threads) > MAX_THREADS:
                for thread in threads:
                    thread.join()
                threads = []

            song_name = self.__get_full_song_name(song)
            thread = threading.Thread(target=self.__download_song, args=(song['youtube_url'], song_name, location))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()


    def load_playlist_from_file(self, file_name: str):
        if file_name is None:
            print("No file name provided")
            return
        
        if not os.path.isfile(file_name):
            print("File does not exist")
            return
            
        with open(file_name, "r", encoding="utf-8") as f:
            self.song_list = json.load(f)



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
        }

        with youtube_dl.YoutubeDL(options) as ydl:
            try:
                ydl.cache.remove()
                ydl.download([video_info['webpage_url']])

            except: # second chance, yes I know this is bad
                ydl.cache.remove()
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

        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def __get_missing_songs(self, location: str = DEFAULT_DOWNLOAD_PATH):
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

    def __get_songs_to_remove(self, location: str = DEFAULT_DOWNLOAD_PATH):
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

    def __get_full_song_name(self, song):
        return song['song_name'] + " - " + song['artist']