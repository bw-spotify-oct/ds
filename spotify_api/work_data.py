import spotipy
import spotipy.util as util
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy.oauth2 as oauth2
from decouple import config
import pandas as pd
from sklearn.preprocessing import StandardScaler
import numpy as np
from numpy.linalg import norm
from joblib import load
from flask import Flask, render_template, request
import random

#CLIENT_ID = config("CLIENT_ID")
#CLIENT_SECRET = config("CLIENT_SECRET")
#credentials = oauth2.SpotifyClientCredentials(
                #    client_id=CLIENT_ID,
                #    client_secret=CLIENT_SECRET)
#token = credentials.get_access_token()

#spotify = spotipy.Spotify(auth=token)
spot_scaler = load('SpotScaler.joblib')

def auth():
    CLIENT_ID = config("CLIENT_ID")
    CLIENT_SECRET = config("CLIENT_SECRET")
    credentials = oauth2.SpotifyClientCredentials(
                    client_id=CLIENT_ID,
                    client_secret=CLIENT_SECRET)
    token = credentials.get_access_token()
    spotify = spotipy.Spotify(auth=token)
    return spotify



# Given a list of songs, select, at most, five of them at random.
# random_song_selector : Vect _ n -> Vect _ (min 5 n)
def random_song_selector(playlist):
    if len(playlist) < 5:
        return playlist
    else:
        return random.sample(playlist, k=5)


# get the ids of 100 recommendations from spotify
# get_100 : {n <= 5} -> Vect (song_id) n -> Vect (song_id) 100
def get_100(target_ids):
    playlist = random_song_selector(target_ids)
    spotify = auth()
    res = spotify.recommendations(seed_tracks=playlist, limit=100)
    ids = [i['id'] for i in res['tracks']]
    return ids


# audio_features_to_dict : Dict (audio_features) -> Dict (mood)
def audio_features_to_dict(feats, has_id=True):
    feat_dict = {'acousticness': feats['acousticness'],
                 'danceability': feats['danceability'],
                 'duration_ms': feats['duration_ms'],
                 'energy': feats['energy'],
                 'instrumentalness': feats['instrumentalness'],
                 'key': feats['key'],
                 'liveness': feats['liveness'],
                 'loudness': feats['loudness'],
                 'mode': feats['mode'],
                 'speechiness': feats['speechiness'],
                 'tempo': feats['tempo'],
                 'time_signature': feats['time_signature'],
                 'valence': feats['valence']}
    if has_id:
       feat_dict['id'] = feats['id']
    return feat_dict


# get_features : Vect (song_id) -> Dict (mood)
def get_features(target_id):
    spotify = auth()
    res = spotify.audio_features(tracks=target_id)[0]

    return audio_features_to_dict(res)


# audio_features_to_df : Vect (Dict (mood)) -> DataFrame (mood)
def audio_features_to_df(feats_list, has_id=True):
    columns = ['acousticness',
               'danceability',
               'duration_ms',
               'energy',
               'instrumentalness',
               'key',
               'liveness',
               'loudness',
               'mode',
               'speechiness',
               'tempo',
               'time_signature',
               'valence']
    if has_id:
        columns.append('id')

    df = pd.DataFrame(columns=columns)
    for feat in feats_list:
        feat_dict = audio_features_to_dict(feat, has_id=has_id)
        df = df.append(feat_dict, ignore_index=True)
    return df


# get_all_features : Vect (song_id) -> DataFrame (mood)
def get_all_features(list_id):
    spotify = auth()
    feats_list = spotify.audio_features(tracks=list_id)

    df = audio_features_to_df(feats_list)

    return df


# Take the mean of the distances between the list of
# recommendations and a feature vector
# NOTE: The mean of the distance is NOT the same
#       as the distance from the mean
# feat_recs : DataFrame (mood) -> Vect (song_id) -> DataFrame (mood)
def feat_recs(target_feats, top_100, k=5):
    df = get_all_features(top_100)

    df_scaled = spot_scaler.transform(df.drop(['id'], axis=1))
    song_df_scaled = spot_scaler.transform(target_feats.drop(['id'], axis=1))

    df['dist'] = [np.mean([norm(x-y) for y in song_df_scaled])
                  for x in df_scaled]
    top = df.sort_values(by='dist').iloc[0:k]

    return top.drop(['dist'], axis=1)


# Take the mean of the distances between the list of
# recommendations and the input options.
# top_recs : Vect (song_id) -> DataFrame (mood)
def top_recs(target_id, k=5):
    return feat_recs(get_all_features(target_id), get_100(target_id), k=k)


# Get an array of data pertaining to a list of recommendations
# songs_data : DataFrame (mood w/ id) -> Vect (Dict (song_data))
def songs_data(res_df):
    vals = res_df.id.values
    song_info = []
    for i in vals:
        song_info.append(songs_data_single(i))
    return song_info


# songs_data_single : String (song_id) -> Dict (song_data)
def songs_data_single(id):
    spotify = auth()
    tracks = spotify.track(id)
    t = {'large_image': tracks['album']['images'][0]['url'],
         'med_image': tracks['album']['images'][1]['url'],
         'small_image': tracks['album']['images'][2]['url'],
         'artist': tracks['artists'][0]['name'],
         'song_name': tracks['name'],
         'id': tracks['id'],
         'uri': tracks['uri']}
    return t


# Get an array of data pertaining to a list of recommendations based on target
# rec_data : Vect (song_id) -> Vect (Dict (song_data))
def rec_data(target_id):
    return songs_data(top_recs(target_id))


# get_songs : String -> Vect (Dict (song_data))
def get_songs(song, limit=7):
    spotify = auth()
    songs = spotify.search(song,
                           limit=limit,
                           offset=0,
                           type='track',
                           market='US')
    tracks = []
    for i in songs['tracks']['items']:
        tracks.append({'song_name': i['name'],
                       'artist': i['artists'][0]['name'],
                       'id': i['id'],
                       'uri': i['uri']})
    return tracks

# get_songs_with_pic : String -> Vect (Dict (song_data))
def get_songs_with_pic(song, limit=7):
    spotify = auth()
    songs = spotify.search(song,
                           limit=limit,
                           offset=0,
                           type='track',
                           market='US')
    tracks = []
    for i in songs['tracks']['items']:
        tracks.append({'large_image': i['album']['images'][0]['url'],
                       'med_image': i['album']['images'][1]['url'],
                       'small_image': i['album']['images'][2]['url'],
                       'song_name': i['name'],
                       'artist': i['artists'][0]['name'],
                       'id': i['id'],
                       'uri': i['uri']})
    return tracks

# construct_mood : Vect Floats -> Dict (mood)
def construct_mood(feats):
    feat_dict = {'acousticness': feats[0],
                 'danceability': feats[1],
                 'duration_ms': feats[2],
                 'energy': feats[3],
                 'instrumentalness': feats[4],
                 'key': feats[5],
                 'liveness': feats[6],
                 'loudness': feats[7],
                 'mode': feats[8],
                 'speechiness': feats[9],
                 'tempo': feats[10],
                 'time_signature': feats[11],
                 'valence': feats[12]}
    return feat_dict


# For testing
# https://spotify-api-helper.herokuapp.com/mood/DReaI4d55IIaiD6P9?acousticness=2&danceability=3&duration_ms=2&energy=9&instrumentalness=6&key=9&liveness=0.14&loudness=7&mode=1&speechiness=.09&tempo=3&time_signature=0.6&valence=.1
# mood : State (mood) (Dict (mood))
def mood():
    acousticness = float(request.args.get('acousticness'))
    danceability = float(request.args.get('danceability'))
    duration_ms = float(request.args.get('duration_ms'))
    energy = float(request.args.get('energy'))
    instrumentalness = float(request.args.get('instrumentalness'))
    key = float(request.args.get('key'))
    liveness = float(request.args.get('liveness'))
    loudness = float(request.args.get('loudness'))
    mode = float(request.args.get('mode'))
    speechiness = float(request.args.get('speechiness'))
    tempo = float(request.args.get('tempo'))
    time_signature = float(request.args.get('time_signature'))
    valence = float(request.args.get('valence'))

    return construct_mood([acousticness,
                           danceability,
                           duration_ms,
                           energy,
                           instrumentalness,
                           key,
                           liveness,
                           loudness,
                           mode,
                           speechiness,
                           tempo,
                           time_signature,
                           valence])


# Sort a list of songs by how similar they are to given mood
# then return top 5
# mood_recs : Vect (song_id) -> Dict (mood) -> DataFrame (mood)
def mood_recs(song_list, mood_feats, k=5):
    scaled_feats = audio_features_to_df([mood_feats], has_id=False)
    df = get_all_features(song_list)

    df_scaled = spot_scaler.transform(df.drop(['id'], axis=1))

    df['dist'] = [norm(x-scaled_feats) for x in df_scaled]
    top = df.sort_values(by='dist').iloc[0:k]

    return top.drop(['dist'], axis=1)


# Given a seed playlist, sort by mood, and use top 5 to get
# 100 recommendations. Sort these recommendations and get another
# top 5, which is then returned.
# http://127.0.0.1:5000/mood_test/0/5ImhD7dhkGVPa0oLiy6R5W?acousticness=2&danceability=1.33&duration_ms=2&energy=.9&instrumentalness=.6&key=.9&liveness=0.14&loudness=.7&mode=1&speechiness=.09&tempo=1.3&time_signature=0.6&valence=.1
# mood_playlist_recs : Vect (song_id) -> State (mood) (Vect (Dict (song_data)))
def mood_playlist_recs(playlist, k=5):
    mood_feats = mood()
    top_5_playlist = mood_recs(playlist, mood_feats, k=k)
    rec_100 = get_100(list(top_5_playlist.id.values))
    top_5 = mood_recs(rec_100, mood_feats, k=k)

    return songs_data(top_5)


# Given a playlist, get a default mood, the mean
# default_mood : Vect (song_id) -> Dict (mood)
def default_mood(playlist):
    df = get_all_features(playlist)
    df_scaled = spot_scaler.transform(df.drop(['id'], axis=1))

    mean_feats = np.mean(df_scaled, axis=0)

    return construct_mood(mean_feats)


# Convert a playlist, represented as a string, into a list.
# playlist_str_to_ls : String -> Vect String
def playlist_str_to_ls(playlist_str):
    return playlist_str.strip('[]').replace("'", '').replace(' ', '').split(',')
