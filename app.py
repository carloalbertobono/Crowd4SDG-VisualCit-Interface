from flask import Flask, render_template, request, Response, session, jsonify
import pandas as pd
import requests
from io import StringIO
from geopy.geocoders import Nominatim
from geotext import GeoText
from config import *
import uuid as myuuid
import copy

# for maps
import folium
from folium.plugins import MarkerCluster
import json
import numpy as np

from params import params as more_params
from functions import failsafe, get_or_setandget, checkmap, check_user_loc, fire_and_forget

app = Flask(__name__)
app.config['SECRET_KEY'] = 'Hola'
geolocator = Nominatim(user_agent="example app")

app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

server = '131.175.120.2:7779'
test = '127.0.0.1:7777'

address = server

# <!--img src= {{ tweets[0][u].url }} height=100 title= '{{tweets[0][u].text + "\n\nUser location: " + tweets[0][u].user_country + "\n\nTweet location: " + tweets[0][u].tweet_location}}' style="display: inline-block;" loading="lazy" onerror="this.style.display='none'"/-->
# <!--img src= {{ tweets[x+1][u].url }} height=100 title='{{tweets[x+1][u].text + "\n\nUser location: " + tweets[x+1][u].user_country + "\n\nTweet location: " + tweets[x+1][u].tweet_location }}' style="display: inline-block;" loading="lazy"/ -->

user_data = {}


# Session - level variables
def get_session_data(session):
    # recover identifier from
    first_time = False
    uuid = get_or_setandget(session, 'uuid', myuuid.uuid1()).hex

    if uuid not in user_data:
        first_time = True
        user_data[uuid] = {}
    my_stuff = user_data[uuid]

    # recover all data locally
    return (get_or_setandget(my_stuff, 'count', 0),
            get_or_setandget(my_stuff, 'applied', []),
            get_or_setandget(my_stuff, 'source_applied', [{'ID': "", 'source': "", 'keywords': ""}]),
            get_or_setandget(my_stuff, 'number_images', 100),
            get_or_setandget(my_stuff, 'tweets', []),
            get_or_setandget(my_stuff, 'csv_contents', []),
            get_or_setandget(my_stuff, 'confidence', 90),
            get_or_setandget(my_stuff, 'confidence_', 0.9),
            get_or_setandget(my_stuff, 'alert', ""),
            get_or_setandget(my_stuff, 'locations', []),
            uuid, first_time, my_stuff)


def set_session_data(session, count, applied, source_applied, number_images, tweets, csv_contents, confidence, confidence_, alert,
                     locations, uuid, mystuff):
    mystuff['count'] = count
    mystuff['applied'] = applied
    mystuff['source_applied'] = source_applied
    mystuff['number_images'] = number_images
    mystuff['tweets'] = tweets
    mystuff['csv_contents'] = csv_contents
    mystuff['confidence'] = confidence
    mystuff['confidence_'] = confidence_
    mystuff['alert'] = alert
    mystuff['locations'] = locations
    user_data[uuid] = mystuff
    return


@app.route('/', methods=['GET', 'POST'])
def index():
    ga = request.cookies.get("_ga")

    # Init all variables at user session level (not globals)
    count, applied, source_applied, number_images, tweets, csv_contents, confidence, confidence_, alert, locations, uuid, first_time, my_stuff = get_session_data(
        session)

    print(applied)
    print(source_applied)
    print(count, len(applied), len(source_applied), len(tweets), len(csv_contents))
    print("GOT REQUEST FROM", uuid, "GA:", ga)

    if request.method == "POST":
        # Before the crawling
        if 'source_button' in request.form:
            # Someone hit search, we just reset (so we should never fall in the "else" branch after the following if)
            count = 0
            source_applied = []
            s0 = {'ID': "", 'source': "", 'keywords': ""}
            source_applied.append(s0)
            applied = []
            tweets = []
            csv_contents = []
            locations = []
            alert = ""

            if count == 0:
                print("Crawling at count 0")
                option = request.form['source']
                keywords = request.form['keywords']
                number_images = request.form['number_pic']
                inputSubreddit = 'all'
                
                if request.form['inputSubreddit']:
                    testsub = request.form['inputSubreddit']
                    print(f'The test sub is {testsub}')
                

                r = requests.post('http://' + address + '/Crawler/API/CrawlCSV',
                                    json={'query': keywords, 'count': number_images, 'preload_images': True, 'source': option, 'subreddit': inputSubreddit})

                if len(r.text) != 1:
                    s = {'ID': count, 'source': option, 'keywords': keywords}
                    source_applied[0] = s

                    f = {'ID': "", 'Filter': "", 'Attribute': "", 'Confidence': 90}
                    applied.append(f)

                    tmp = StringIO(r.text)
                    df = pd.read_csv(tmp)
                    print(df.columns)
                    failsafe(df)

                    u = []
                    for x in range(len(df)):
                        p = {"url": df['media_url'].iloc[x], "text": df['full_text'].iloc[x],
                             "user_country": df['user_country'].iloc[x], "tweet_location": df['CIME_geolocation_string'].iloc[x],
                             "id": df['id'].iloc[x], "checked": True}
                        u.append(p)
                        continue  # TODO: we are bypassing geo enrichment her

                        user_loc = df['user_loc'].iloc[x]
                        geolocated_text = geolocator.geocode(user_loc, timeout=10)
                        if geolocated_text == None:
                            full_location_list = GeoText(user_loc).cities + GeoText(user_loc).countries
                            full_location = ''.join(str(e) for e in full_location_list)
                            geolocated_full_location = geolocator.geocode(full_location, timeout=10)
                            if geolocated_full_location == None:
                                df['user_country'].iloc[x] = 'Not defined'
                            else:
                                df['user_country'].iloc[x] = geolocated_full_location.address.split(', ')[-1]
                        else:
                            df['user_country'].iloc[x] = geolocated_text.address.split(', ')[-1]


                    tweets.append(u)
                    if 'user_country' in df:
                        df_sorted = df.sort_values(by=['user_country'], ascending=True)
                        locations.append(df_sorted['user_country'].astype(str).unique().tolist())
                    csv_string = df.to_csv(encoding="utf-8", index=None)
                    # csv_contents.append(url_csv_get.text)
                    csv_contents.append(csv_string)
                    count += 1
                    alert = ""

                else:
                    alert = "Your search query did not return any images. Please try to either shorten the query or make use of the OR keyword to make some of the terms optional. Also refer to the <a href=\"https://developer.twitter.com/en/docs/twitter-api/v1/rules-and-filtering/search-operators\">Twitter user guide</a>"
            else:
                print("Crawling not as count 0")
                option = request.form['source']
                keywords = request.form['keywords']
                number_images = request.form['number_pic']
                inputSubreddit = 'all'
                
                r = requests.post('http://' + address + '/Crawler/API/CrawlCSV',
                                    json={'query': keywords, 'count': number_images, 'preload_images': True, 'source': option, 'subreddit': inputSubreddit})
                    
                if len(r.text) != 1:
                    s = {'ID': 0, 'source': option, 'keywords': keywords}
                    source_applied[0] = s

                    tmp = StringIO(r.text)
                    df = pd.read_csv(tmp)
                    failsafe(df)

                    u = []
                    for x in range(len(df)):

                        p = {"url": df['media_url'].iloc[x], "text": df['full_text'].iloc[x],
                             "user_country": df['user_country'].iloc[x], "tweet_location": df['CIME_geolocation_string'].iloc[x],
                             'id': df['id'].iloc[x]}
                        u.append(p)
                        continue  # TODO: we are bypassing geo enrichment here

                        user_loc = df['user_loc'].iloc[x]
                        geolocated_text = geolocator.geocode(user_loc, timeout=10)
                        if geolocated_text == None:
                            full_location_list = GeoText(user_loc).cities + GeoText(user_loc).countries
                            full_location = ''.join(str(e) for e in full_location_list)
                            geolocated_full_location = geolocator.geocode(full_location, timeout=10)
                            if geolocated_full_location == None:
                                df['user_country'].iloc[x] = 'Not defined'
                            else:
                                df['user_country'].iloc[x] = geolocated_full_location.address.split(', ')[-1]
                        else:
                            df['user_country'].iloc[x] = geolocated_text.address.split(', ')[-1]

                    tweets[0] = u

                    df_sorted = df.sort_values(by=['user_country'], ascending=True)
                    locations[0] = df_sorted['user_country'].astype(str).unique().tolist()
                    csv_string = df.to_csv(encoding="utf-8", index=None)
                    # csv_contents[0]= url_csv_get.text
                    csv_contents[0] = csv_string
                    alert = ""
                else:
                    alert = "Your search query did not return any images. Please try to either shorten the query or make use of the OR keyword to make some of the terms optional"
        # After the crawling
        elif 'apply_button' in request.form:
            if int(request.form['apply_button']) == count:
                print("EQUAL COUNT - ADD")
                extraparams = {}
                if request.form['Filter_select'] != "" and request.form['Filter_select'] != d['user_location_sel_tag']:

                    Filter = request.form['Filter_select']
                    if request.form['Filter_select'] == d['duplicates_tag']:
                        attribute = "PHashDeduplicator"
                        extraparams['bits'] = request.form['bit']
                    elif request.form['Filter_select'] == d['meme']:
                        attribute = "MemeClassifier"
                    elif request.form['Filter_select'] == d['scene_tag']:
                        attribute = 'SceneClassifier'
                        extraparams['object'] = request.form['option1_select']
                    elif request.form['Filter_select'] == d['object_tag']:
                        attribute = 'YOLOv5ObjectDetector'
                        extraparams['object'] = request.form['option2_select']
                    elif request.form['Filter_select'] == d['person_tag']:
                        attribute = 'YOLOv5ObjectDetector'
                        extraparams['object'] = 'person'
                    elif request.form['Filter_select'] == d['object_tag_detr']:
                        attribute = 'DETRObjectClassifier'
                        extraparams['object'] = request.form['option_obj_select']
                    elif request.form['Filter_select'] == d['flood_tag']:
                        attribute = "FloodClassifier"
                    elif request.form['Filter_select'] == d["nsfw_tag"]:
                        attribute = "NSFWClassifier"
                    elif request.form['Filter_select'] == d['post_location_tag']:
                        attribute = "CimeAugmenter"
                    elif request.form['Filter_select'] == "Add user country":
                        attribute = "GeotextAugmenter"
                    elif request.form['Filter_select'] == d['user_location_tag']:
                        attribute = "GeotextAugmenter"
                    # else:
                    #    attribute = [request.form['latitude_text'], request.form['longitude_text']]
                    confidence_ = request.form['confidence']
                    confidence = float(confidence_) / 100

                    min_items = request.form['min_items']
                    print("###", min_items)

                    # url_csv = "https://polimi365-my.sharepoint.com/:x:/g/personal/10787953_polimi_it/EczlUzJfhFdFjwNqc8NThlQB-pYmb6CbxDZbxbwB4xHQCQ?Download=1"
                    params = {'filter_name_list': [attribute],
                              # 'confidence_threshold_list': [float(attribute.split()[1])],
                              'confidence_threshold_list': [confidence],
                              'column_name': 'media_url',
                              'csv_file': csv_contents[count - 1]
                              }

                    # build filters
                    filter_params = {'confidence': confidence}
                    for k, v in extraparams.items():
                        filter_params[k] = v
                    filter_params['name'] = attribute
                    extraparams['name'] = attribute
                    if min_items: filter_params['min_items'] = min_items

                    params = {'actions': [filter_params],
                              'column_name': 'media_url',
                              'csv_file': csv_contents[count - 1]
                              }

                    print(params['actions'])

                    r = requests.post(url='http://' + address + '/Action/API/FilterCSV', json=params)

                    if len(r.text) > 160:
                        f = {'ID': count, 'Filter': Filter, 'Attribute': attribute, 'Confidence': confidence_, "min_items": min_items}
                        f = {**extraparams, **f}
                        k = {'ID': "", 'Filter': "", 'Attribute': "", 'Confidence': 90}
                        applied[count - 1] = f
                        applied.append(k)

                        csv_contents.append(r.text)
                        tmp = StringIO(r.text)
                        df = pd.read_csv(tmp)
                        failsafe(df)

                        df_sorted = df.sort_values(by=['user_country'], ascending=True)
                        locations.append(df_sorted['user_country'].astype(str).unique().tolist())
                        u = []
                        for x in range(len(df)):
                            p = {"url": df['media_url'].iloc[x], "text": df['full_text'].iloc[x],
                                 "user_country": df['user_country'].iloc[x], "tweet_location": df['CIME_geolocation_string'].iloc[x],
                                 "id": df['id'].iloc[x], "checked": True}
                            u.append(p)
                        tweets.append(u)
                        count += 1
                        alert = ""
                    else:
                        alert = "After running the above filter, no images remain. Either increase the number of images or change the filter. (1)"

                elif request.form['Filter_select'] == d['user_location_sel_tag']:
                    Filter = d['user_location_sel_tag']
                    attribute = request.form['option3_select']
                    f = {'ID': count, 'Filter': Filter, 'Attribute': attribute, 'Confidence': confidence_}
                    k = {'ID': "", 'Filter': "", 'Attribute': "", 'Confidence': 90}
                    applied[count - 1] = f
                    applied.append(k)

                    tmp = StringIO(csv_contents[count - 1])
                    df0 = pd.read_csv(tmp)
                    df = df0.loc[df0['user_country'] == attribute]
                    failsafe(df)

                    df_sorted = df.sort_values(by=['user_country'], ascending=True)
                    locations.append(df_sorted['user_country'].astype(str).unique().tolist())
                    u = []
                    for x in range(len(df)):
                        p = {"url": df['media_url'].iloc[x], "text": df['full_text'].iloc[x], "user_country": df['user_country'].iloc[x],
                             "tweet_location": df['CIME_geolocation_string'].iloc[x], "id": df['id'].iloc[x], "checked": True}
                        u.append(p)
                    tweets.append(u)
                    csv_string = df.to_csv(encoding="utf-8", index=None)
                    csv_contents.append(csv_string)
                    count += 1
                    alert = ""

            # else:
            #    flash('Select an option')
            #    applied[count-1]['Filter'] = ""

            # not last request
            else:

                sel_count = int(request.form['apply_button'])
                print("NOT LAST", sel_count)

                print("FIRST", count, len(applied), len(source_applied), len(tweets), len(csv_contents))

                extraparams = {}

                if request.form['Filter_select'] != "" and request.form['Filter_select'] != d['user_location_sel_tag']:
                    Filter = request.form['Filter_select']
                    if request.form['Filter_select'] == d['duplicates_tag']:
                        attribute = "PHashDeduplicator"
                        extraparams['bits'] = request.form['bit']
                    elif request.form['Filter_select'] == d['meme']:
                        attribute = "MemeClassifier"
                    elif request.form['Filter_select'] == d['scene_tag']:
                        attribute = 'SceneClassifier'
                        extraparams['object'] = request.form['option1_select']
                    elif request.form['Filter_select'] == d['object_tag']:
                        attribute = 'YOLOv5ObjectDetector'
                        extraparams['object'] = request.form['option2_select']
                    elif request.form['Filter_select'] == d['person_tag']:
                        attribute = 'YOLOv5ObjectDetector'
                        extraparams['object'] = 'person'
                    elif request.form['Filter_select'] == d['object_tag_detr']:
                        attribute = 'DETRObjectClassifier'
                        extraparams['object'] = request.form['option_obj_select']
                    elif request.form['Filter_select'] == d['flood_tag']:
                        attribute = "FloodClassifier"
                    elif request.form['Filter_select'] == d["nsfw_tag"]:
                        attribute = "NSFWClassifier"
                    elif request.form['Filter_select'] == d['post_location_tag']:
                        attribute = "CimeAugmenter"
                    elif request.form['Filter_select'] == d['user_location_tag']:
                        attribute = "GeotextAugmenter"
                    else:
                        attribute = [request.form['latitude_text'], request.form['longitude_text']]

                    confidence_ = request.form['confidence']  # form value
                    confidence = float(confidence_) / 100  # post value

                    min_items = request.form['min_items']

                    # build filters
                    filter_params = {'confidence': confidence}
                    if min_items: filter_params['min_items'] = min_items

                    filter_params['name'] = attribute
                    extraparams['name'] = attribute

                    for k, v in extraparams.items():
                        filter_params[k] = v
                    params = {'actions': [filter_params],
                              'column_name': 'media_url',
                              'csv_file': csv_contents[sel_count - 1]
                              }

                    print(2, params['actions'])

                    r = requests.post(url='http://' + address + '/Action/API/FilterCSV', json=params)
                    # print(len(r.text))
                    if len(r.text) > 160:
                        f = {'ID': sel_count, 'Filter': Filter, 'Attribute': attribute, 'Confidence': confidence_, 'min_items': min_items}
                        f = {**extraparams, **f}
                        applied[sel_count - 1] = f
                        k = {'ID': "", 'Filter': "", 'Attribute': "", 'Confidence': 90}
                        applied[sel_count] = k

                        csv_contents[sel_count] = r.text
                        # url_csv_get = requests.get(url_csv)
                        # url_request = io.StringIO(url_csv_get.content.decode('utf-8'))
                        tmp = StringIO(r.text)
                        df = pd.read_csv(tmp)

                        failsafe(df)

                        df_sorted = df.sort_values(by=['user_country'], ascending=True)
                        locations[sel_count] = df_sorted['user_country'].astype(str).unique().tolist()
                        u = []
                        for x in range(len(df)):
                            p = {"url": df['media_url'].iloc[x], "text": df['full_text'].iloc[x],
                                 "user_country": df['user_country'].iloc[x], "tweet_location": df['CIME_geolocation_string'].iloc[x],
                                 "id": df['id'].iloc[x], "checked": True}
                            u.append(p)
                        tweets[sel_count] = u
                        alert = ""
                    else:
                        alert = "After running the above filter, no images remain. Either increase the number of images or change the filter. (2)"

                # elif request.form['Filter_select'] == d['user_location_sel_tag'] :
                #    Filter = d['user_location_sel_tag']
                #    attribute = request.form['option3_select']
                #    f = {'ID': sel_count, 'Filter': Filter, 'Attribute': attribute, 'Confidence': confidence_}
                #    applied[sel_count-1] = f
                #    tmp = StringIO(csv_contents[sel_count-1])
                #    df0 = pd.read_csv(tmp)
                #    df = df0.loc[df0['user_country'] == attribute]
                #    failsafe(df)
                #    df_sorted = df.sort_values(by=['user_country'], ascending = True)
                #    locations[sel_count]= df_sorted['user_country'].astype(str).unique().tolist()
                #    u = []
                #    for x in range(len(df)):
                #        p = {"url": df['media_url'].iloc[x], "text": df['full_text'].iloc[x], "user_country": df['user_country'].iloc[x], "tweet_location": df['CIME_geolocation_string'].iloc[x]}
                #        u.append(p)
                #    tweets[sel_count]= u
                #    csv_string = df.to_csv(encoding= "utf-8")
                #    csv_contents[sel_count]= csv_string
                #    alert = ""

                source_applied = source_applied[:2]
                applied = applied[:sel_count + 1]
                tweets = tweets[:sel_count + 1]
                csv_contents = csv_contents[:sel_count + 1]
                locations = locations[:sel_count + 1]

                count = sel_count + 1

                print("THEN", count, len(applied), len(source_applied), len(tweets), len(csv_contents))
        # else:
        #    flash('Select an option')
        #    applied[sel_count-1]['Filter'] = ""
        elif 'reset_button' in request.form:
            count = 0
            source_applied = []
            s0 = {'ID': "", 'source': "", 'keywords': ""}
            source_applied.append(s0)
            applied = []
            tweets = []
            csv_contents = []
            locations = []
            alert = ""
        elif 'up_button' in request.form:

            sel_count = int(request.form['up_button'])

            a = applied[sel_count - 2]
            applied[sel_count - 2] = applied[sel_count - 1]
            applied[sel_count - 1] = a

            for a in range(count - sel_count + 1):
                if applied[sel_count - 2 + a]['Filter'] != d['user_location_sel_tag']:
                    params = {'filter_name_list': [applied[sel_count - 2 + a]['Attribute']],
                              'confidence_threshold_list': [int(applied[sel_count - 2 + a]['Confidence']) / 100],
                              'column_name': 'media_url',
                              'csv_file': csv_contents[sel_count - 2 + a]
                              }
                    params = {'actions': [{'name': applied[sel_count - 2 + a]['Attribute'],
                                           'confidence': int(applied[sel_count - 2 + a]['Confidence']) / 100}],
                              'column_name': 'media_url',
                              'csv_file': csv_contents[sel_count - 2 + a]
                              }

                    print("hmm...")
                    r = requests.post(url='http://' + address + '/Action/API/FilterCSV', json=params)
                    if len(r.text) > 160:

                        csv_contents[sel_count - 1 + a] = r.text
                        tmp = StringIO(r.text)
                        df = pd.read_csv(tmp)
                        failsafe(df)

                        df_sorted = df.sort_values(by=['user_country'], ascending=True)
                        locations[sel_count - 1 + a] = df_sorted['user_country'].astype(str).unique().tolist()
                        u = []
                        for x in range(len(df)):
                            p = {"url": df['media_url'].iloc[x], "text": df['full_text'].iloc[x],
                                 "user_country": df['user_country'].iloc[x], "tweet_location": df['CIME_geolocation_string'].iloc[x],
                                 "id": df['id'].iloc[x], "checked": df['checked'].iloc[x]}
                            u.append(p)
                        tweets[sel_count - 1 + a] = u
                        alert = ""
                    # pass
                    else:
                        print(r.text)
                        alert = "After running the above filter, no images remain. Either increase the number of images or change the filter. (3)"
                        break
                else:
                    tmp = StringIO(csv_contents[sel_count - 2 + a])
                    df0 = pd.read_csv(tmp)
                    df = df0.loc[df0['user_country'] == applied[sel_count - 2 + a]['Attribute']]
                    failsafe(df)

                    csv_string = df.to_csv(encoding="utf-8", index=None)
                    print("The length is", len(csv_string))
                    if len(csv_string) > 160:
                        print("location: ", applied)
                        df_sorted = df.sort_values(by=['user_country'], ascending=True)
                        locations[sel_count - 1 + a] = df_sorted['user_country'].astype(str).unique().tolist()
                        u = []
                        for x in range(len(df)):
                            p = {"url": df['media_url'].iloc[x], "text": df['full_text'].iloc[x],
                                 "user_country": df['user_country'].iloc[x], "tweet_location": df['CIME_geolocation_string'].iloc[x],
                                 "id": df['id'].iloc[x], "checked": df['checked'].iloc[x]}
                            u.append(p)
                        tweets[sel_count - 1 + a] = u
                        csv_contents[sel_count - 1 + a] = csv_string
                        alert = ""
                    else:
                        alert = "After running the above filter, no images remain. Either increase the number of images or change the filter. (4)"
                        break
        else:
            # url_download = int(request.form['download_button'])
            # with open('result1.csv', 'w+', encoding= "utf-8") as file:
            #    file.write(csv_contents[url_download])
            pass

    # Keep track of user data at session level
    set_session_data(session, count, applied, source_applied, number_images, tweets, csv_contents, confidence, confidence_, alert,
                     locations, uuid, my_stuff)

    has_map, df = checkmap(csv_contents)
    has_user_loc = check_user_loc(csv_contents)
    map_data = map(small=True) if has_map else None

    # Tracking
    if ga:
        track_event(ga)

    return render_template('index.html', count=count, source_applied=source_applied, tweets=tweets,
                           applied=applied, alert=alert, locations=locations,
                           number_images=number_images, confidence=confidence, hasmap=has_map, mapdata=map_data,
                           moreparams=more_params, firsttime=first_time, hasuserloc=has_user_loc)


@app.route("/downloadCSV")
def downloadCSV():
    # print("length of csv_contents: ", len(csv_contents))
    # print("int(request.args.get('id')): ", int(request.args.get('id')))
    # print("csv_contents:\n\n", csv_contents)

    count, applied, source_applied, number_images, tweets, csv_contents, confidence, confidence_, alert, locations, uuid, firsttime, mystuff = get_session_data(
        session)

    # rename "media_url" in "info_media_url"
    df_ = csv_contents[int(request.args.get('id'))]
    tmp = StringIO(df_)
    df_ = pd.read_csv(tmp)
    df_ = df_.rename(columns={"media_url": "url"}, errors='ignore')

    if 'CIME_geolocation_centre_first' in df_:
        df_ = df_.drop(columns=['CIME_geolocation_centre_first',
                                'CIME_geolocation_string_first',
                                'CIME_geolocation_osm_first'], errors='ignore')

    df_ = df_.fillna('-').replace(r'^\s*$', '-', regex=True)
    res = df_.to_csv(encoding="utf-8", index=None)

    return Response(
        # csv_contents[int(request.args.get('id'))],
        res,
        mimetype="text/csv",
        headers={"Content-disposition":
                     "attachment; filename=download.csv"})


@app.route("/downloadCSVs")
def downloadCSVs():
    # print("length of csv_contents: ", len(csv_contents))
    # print("int(request.args.get('id')): ", int(request.args.get('id')))
    # print("csv_contents:\n\n", csv_contents)

    count, applied, source_applied, number_images, tweets, csv_contents, confidence, confidence_, alert, locations, uuid, firsttime, mystuff = get_session_data(
        session)

    # rename "media_url" in "info_media_url"
    df_ = csv_contents[int(request.args.get('id'))]
    tmp = StringIO(df_)
    df_ = pd.read_csv(tmp)
    df_ = df_.rename(columns={"media_url": "info_media_url"}, errors='ignore')

    # Cosmetics for RCIS 22
    df_ = df_.rename(columns={"info_media_url": "url"})
    import ast
    # df_['CIME_geolocation_centre_first'] = df_['CIME_geolocation_centre_first'].apply(lambda x: ast.literal_eval(x)).apply(lambda x: str(x[0]) + ',' + str(x[1]))
    df_['gpe_lat'] = df_['CIME_geolocation_centre_first'].apply(lambda x: ast.literal_eval(x)).apply(lambda x: str(x[0]))
    df_['gpe_lon'] = df_['CIME_geolocation_centre_first'].apply(lambda x: ast.literal_eval(x)).apply(lambda x: str(x[1]))
    df_ = df_.rename(columns={"CIME_geolocation_string_first": "gpe"}, errors='ignore')

    df_ = df_.drop(columns=['CIME_geolocation_centre',
                            'CIME_geolocation_string',
                            'CIME_geolocation_osm',
                            'CIME_geolocation_centre_first'], errors='ignore')

    df_ = df_.fillna('-').replace(r'^\s*$', '-', regex=True)
    res = df_.to_csv(encoding="utf-8", index=None)

    return Response(
        # csv_contents[int(request.args.get('id'))],
        res,
        mimetype="text/csv",
        headers={"Content-disposition":
                     "attachment; filename=download.csv"})


@app.route('/map', methods=['GET', 'POST'])
def map(small=False):
    count, applied, source_applied, number_images, tweets, csv_contents, confidence, confidence_, alert, locations, uuid, firsttime, mystuff = get_session_data(
        session)

    hasmap, df = checkmap(csv_contents)
    if not hasmap:
        return "Not initialized"

    # parse json
    cimelist = df['CIME_geolocation_centre'].replace('None', np.nan).fillna('[]').apply(json.loads)
    # get first
    df['CIME_geolocation_centre_first'] = cimelist.apply(lambda l: [l[0][1], l[0][0]] if l else None)

    # OR explode?
    # keep = df.columns.to_list()
    # keep.remove('CIME_geolocation_centre')
    # keep.remove('CIME_geolocation_string')
    # keep.remove('CIME_geolocation_osm')
    # df = df.set_index(keep).apply(pd.Series.explode).reset_index()

    # get valid
    dfout = df[~df['CIME_geolocation_centre_first'].isnull()]

    # other fields
    import ast
    dfout.CIME_geolocation_osm = dfout.CIME_geolocation_osm.apply(lambda x: ast.literal_eval(x))
    dfout.CIME_geolocation_string = dfout.CIME_geolocation_string.apply(lambda x: ast.literal_eval(x))
    dfout['CIME_geolocation_osm_first'] = dfout['CIME_geolocation_osm'].apply(lambda x: x[0])
    dfout['CIME_geolocation_string_first'] = dfout['CIME_geolocation_string'].apply(lambda x: x[0])

    # stuff it back
    lastid = len(csv_contents) - 1
    csv_contents[lastid] = dfout.to_csv(encoding="utf-8", index=None)

    # to records
    records = dfout[['full_text', 'media_url', 'CIME_geolocation_centre_first']].to_dict('records')

    if small:
        f = folium.Figure(width='50%')
        m = folium.Map(location=[10.0, 0.0], tiles="cartodbpositron", zoom_start=2)
        m.add_to(f)
    # m = folium.Map(location=[10.0, 0.0], tiles="cartodbpositron", zoom_start=1, height='30%', width='40%', left ='30%', right='30%', padding='0%')
    else:
        m = folium.Map(location=[10.0, 0.0], tiles="cartodbpositron", zoom_start=3)

    mk = MarkerCluster()
    fg = folium.FeatureGroup(name='')

    for r in records:
        ma = folium.Marker(
            location=r['CIME_geolocation_centre_first'],
            popup='<p>' + r['full_text'] + '</p>' + '<img src="' + r['media_url'] + '" height=100>',
            icon=folium.Icon(color="red", icon="info-sign"),
        )
        mk.add_child(ma)

    fg.add_child(mk)
    m.add_child(fg)

    if small:
        h = f._repr_html_()
        h = h.replace("position:relative;width:100%;height:0;padding-bottom:60%;",
                      "position:relative;width:100%;height:0;padding-bottom:60vh;")
    else:
        h = m._repr_html_()
    return h


@app.route('/batch', methods=['GET', 'POST'])
def batch():
    count, applied, source_applied, number_images, tweets, csv_contents, confidence, confidence_, alert, locations, uuid, firsttime, mystuff = get_session_data(
        session)

    j = {'url': f'http://{address}/Crawler/API/CrawlAndFilter',
         'count': '...',
         'csv_file': '...',
         'column_name': 'media_url',
         'source': source_applied[0]['source'],
         'query': source_applied[0]['keywords'],
         'actions': []}

    filters = applied[:-1]
    for f in filters:
        f = copy.deepcopy(f)
        config = f
        config['name'] = f['Attribute']
        del config['Attribute']
        del config['ID']
        config['confidence'] = "{:.2f}".format(float(config['Confidence']) / 100)
        del config['Confidence']
        del config['Filter']

        j['actions'].append(config)

    return jsonify(j)


# TODO: create a uuid for each client and use that
GA_TRACKING_ID = "UA-210743922-1"  # "UA-208620802-1"


# Do it async
@fire_and_forget
def track_event(cid, type='event', category='test', action='test', label='test', value=1, tracking_id=GA_TRACKING_ID):
    data = {
        'v': '1',  # API Version.
        'tid': tracking_id,  # Tracking ID / Property ID.
        # Anonymous Client Identifier. Ideally, this should be a UUID that
        # is associated with particular user, device, or browser instance.
        'cid': cid,
        't': type,  # Event hit type.
        'ec': category,  # Event category.
        'ea': action,  # Event action.
        'el': label,  # Event label.
        'ev': value,  # Event value, must be an integer
        'ua': 'Crowd4SDG Visualcit Backend'
    }
    print(data)

    response = requests.post('https://www.google-analytics.com/collect', data=data)
    print(response.text)


if __name__ == '__main__':
    app.config['SESSION_TYPE'] = 'filesystem'
    # app.config['SERVER_NAME'] = address
    # app.config['SESSION_COOKIE_DOMAIN'] = address
    # app.config['REMEMBER_COOKIE_SECURE'] = False
    # app.config['SESSION_COOKIE_SECURE'] = False
    # app.config['SESSION_COOKIE_SAMESITE'] = 'None'
    # app.config['SESSION_COOKIE_HTTPONLY'] = True
    # app.config['SESSION_COOKIE_NAME'] = "visualcit_session"
    # sess.init_app(app)
    # print(app.config)
    app.run(debug=True, use_reloader=True)


@app.context_processor
def inject_tags():
    return get_tags()
