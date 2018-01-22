import logging
import re
import requests
import csv
import random
from cStringIO import StringIO
from werkzeug.datastructures import Headers
from werkzeug.wrappers import Response
from flask import Flask, render_template, request, stream_with_context
from urlparse import urlparse
from classify_text import classify

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/upload', methods=['POST'])
def upload_csv():

    # capture post variables
    radio_append = request.form['radio_append']

    if 'root_domains' in request.form:
        root_domains = 'on'
    else:
      root_domains = 'off'

    print root_domains + radio_append

    if not request.files['data_file']:
      return "No file"

    def generate():
      new_data = StringIO()
      reader = csv.DictReader(request.files['data_file'])
      new_fields = []

      # retain columns if appending to existing csv
      if radio_append == 'on':
        new_fields = reader.fieldnames
      else:
        new_fields.append('url')
 
      # add new fields
      new_fields.extend(['category_a', 'confidence_a', 'category_b', 'confidence_b', 'category_c', 'confidence_c'])

      if root_domains == 'on':
        new_fields.append('root_domain')

      writer = csv.DictWriter(new_data, fieldnames=new_fields)
      writer.writeheader()

      # process uploaded file
      for row in reader:

        categories = classify_url(row['url'])
        root_domain = urlparse(row['url']).hostname
        field_data = {}

        # write all the info back into fresh CSV (the hard way?)
        for field in new_fields:
          if field == 'url' and len(categories) > 0:
            field_data[field] = row[field]
          elif field == 'category_a' and len(categories) > 0:
            field_data[field] = categories[0]['name']
          elif field == 'confidence_a' and len(categories) > 0:
            field_data[field] = categories[0]['confidence']
          elif field == 'category_b'and len(categories) > 1:
            field_data[field] = categories[1]['name']
          elif field == 'confidence_b' and len(categories) > 1:
            field_data[field] = categories[1]['confidence']
          elif field == 'category_c' and len(categories) > 2:
            field_data[field] = categories[2]['name']
          elif field == 'confidence_c' and len(categories) > 2:
            field_data[field] = categories[2]['confidence']
          elif field == 'root_domain':
            field_data[field] = root_domain
          else:
            if radio_append == 'on':
              field_data[field] = row[field]

        writer.writerow(field_data)

      yield new_data.getvalue()

    # random filename
    filename = str(random.randint(1000000,9999999)) + '.csv'
    headers = Headers()
    headers.set('Content-Disposition', 'attachment', filename=filename)

    # stream the response as the data is generated
    return Response(
        stream_with_context(generate()),
        mimetype='text/csv', headers=headers
    )

@app.errorhandler(500)
def server_error(e):
    logging.exception('An error occurred during a request.')
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500

def classify_url(url):
  setheaders = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
  'Accept-Encoding': 'none',
  'Accept-Language': 'en-US,en;q=0.8',
  'Connection': 'keep-alive'}

  # if error, return NA category
  try:
      page = requests.get(url, headers=setheaders)
      html = page.text.encode('utf-8', 'ignore')
      try:
        categories = classify(html)
        return categories
      except:
        print "Google classification failed"
        return [{'name': 'NA', 'confidence': 0}]
  except requests.exceptions.RequestException as e:
      print "Error getting URL"
      return [{'name': 'NA', 'confidence': 0}]

if __name__ == '__main__':
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
