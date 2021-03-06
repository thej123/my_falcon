# import json

import io
import os
import re
import uuid
import mimetypes

import falcon
import msgpack

# List of media types the service will accept.
ALLOWED_IMAGE_TYPES = (
    'image/gif',
    'image/jpeg',
    'image/png',
)

# Checks incoming media type to make sure it is a common image type. 
# For this we will implement a `before` hook.

# Hooks must accept four arguments. The first 2 arguments, a reference to the same `req` and `resp` 
# objects that are passed into responders. The `resource` argument is a Resource instance 
# associated with the request. The fourth argument, named `params` by convention, is a reference to 
# the kwarg dictionary Falcon created with each request. `params` will contain the route's URI 
# template params and their values.
def validate_image_types(req, resp, resource, params):
    if req.content_type not in ALLOWED_IMAGE_TYPES:
        msg = 'Image Type not allowed. Must be PNG, JPEG, or GIF'
        raise falcon.HTTPBadRequest('Bad request', msg)

# you can also use `resp` to play with the HTTP response as needed, and you can even use hooks to 
# inject extra kwargs.
def extract_project_id(req, resp, resource, params):
    # Adds `project_id` to the list of params for all responders. Meant to be used as a `before` hook.
    params['project_id'] = req.get_header('X-PROJECT-ID')

# Hooks can be applied to an entire resource by simple decorating the class.
# @falcon.before(extract_project_id)
class Collection(object):

    """
    _CHUNK_SIZE_BYTES = 4096

    # The resource object must now be initialized with a path used during POST.
    def __init__(self, storage_path):
        self._storage_path = storage_path
        # modified `app.py` and passed in a path to the initializer.
    """

    def __init__(self, image_store):
        self._image_store = image_store

    def on_get(self, req, resp):
        doc = {
            'images': [
                {
                    'href': '/images/1eaf6ef1-7f2d-4ecc-a8d5-6e8adba7cc0e.png'
                }
            ]
        }

        # resp.body = json.dumps(doc, ensure_ascii=False)

        resp.data = msgpack.packb(doc, use_bin_type=True)
        # NOTE the use of `resp.data` in lieu of `resp.body`. If you assign a bytestring to the 
        # later, Falcon will figure it out, but you can realize a small performance gain by 
        # assigning directly to `resp.data`.

        resp.content_type = falcon.MEDIA_MSGPACK
        # The `falcon` module provides a number of constants for common media types, including 
        # `falcon.MEDIA_JSON`, `falcon.MEDIA_XML`, etc.

        # The following line can be ommitted because 200 is the default status returned by the 
        # framework, but it is included here to illistrate how this may be overridden as needed.
        resp.status = falcon.HTTP_200
    
    # For any HTTP method you want your resource to support, simply add an `on_*()` method to the class.

    # on_get(), on_post(), on_head(), etc are called `responders`.
    # Hook will run before each request to post a message.
    @falcon.before(validate_image_types)
    def on_post(self, req,resp):
        """
        ext = mimetypes.guess_extension(req.content_type)
        name = '{uuid}{ext}'.format(uuid=uuid.uuid4(), ext=ext)
        # Generate a unique name for the image
        image_path = os.path.join(self._storage_path, name)

        with io.open(image_path, 'wb') as image_file:
            while True:
                chunk = req.stream.read(self._CHUNK_SIZE_BYTES)
                # reading from `req.stream`
                # It's called `stream` instead of `body` to emphasize that you are really reading from an input stream; by default Falcon does not spool or decode request data, instead giving you direct access to the incoming binary stream provided by the WSGI server.
                if not chunk:
                    break
                
                image_file.write(chunk)
                # writing it out on `image_file`
        """

        name = self._image_store.save(req.stream, req.content_type)
        resp.status = falcon.HTTP_201
        resp.location = '/images/' + name
        # We used `falcon.HTTP_201` to set the response status to "201 Created". We could also use 
        # `falcon.HTTP_CREATED` alias.

        # The `Request` and `Response` classes contain convent attributes for reading and setting 
        # common headers, but you can always access any header by name with the `req.get_header()` 
        # and `resp.set_header()` methods.

# Class to represent a single image resource.
class Item(object):
    
    def __init__(self, image_store):
        self._image_store = image_store
    
    def on_get(self, req, resp, name):
        # Any URI parameters that you specify in your routes will be turned into corresponding kwargs and passed into the target responder as such.
        resp.content_type = mimetypes.guess_type(name)[0]
        # Set the Content-Type header based on the filename extension.

        try:
            resp.stream, resp.stream_len = self._image_store.open(name)
            # Stream out the image directly from an open file handle.
            # Whenever using `resp.stream` instead of `resp.body` or `resp.data`, you typically also 
            # specify the expected lenth of the stream so that the web client knows how much data to 
            # read from the response. We do this using `resp.stream_len`
        except IOError:
            # Falcon assumes that resource responders (`on_get()`, `on_post()`, etc.) will do the right 
            # thing. Falcon doesn't try to protect responder code from itself. This approach reduces the 
            # number of extraneous checks that Falcon would otherwise have to perform, making the 
            # framework more efficient. Falcon generally requires that:
            # 1. Resource responders set response variables to sane values.
            # 2. Untrusted input (i.e., input from an external client or service) is validated.
            # 3. Your code is well-tested, with high code coverage
            # 4. Errors are anticipated, detected, logged and handled appropriately within each responder 
            # or by global error handling hooks.

            # When it comes to error handling, you can always directly set the error status, appropriate 
            # response headers and error body using the `resp` object. Falcon provides a set of error 
            # classes you can raise when something goes wrong. Falcon will convert an instance or subclass 
            # of `falcon.HTTPError` raised by a responder, hook or middleware component into an 
            # appropriate HTTP response.

            # Normally you would also log the error.
            raise falcon.HTTPNotFound()

# Earlier our POST test relied heavily on mocking, relying on assumptions that may or may not hold 
# true as the code evolves. To mitigate this problem, we will refractor the tests and the application.
class ImageStore(object):
    
    __CHUNK_SIZE_BYTES = 4096
    _IMAGE_NAME_PATTERN = re.compile(
        '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.[a-z]{2,4}$'
    )
    # 217d4814-58c0-49e1-877f-f84a17323df4.png

    # Note the use of dependency injection for standard library methods. We'll use these later to 
    # avoid monkey-patching.
    def __init__(self, storage_path, uuidgen=uuid.uuid4, fopen=io.open):
        self._storage_path = storage_path
        self._uuidgen = uuidgen
        self._fopen = fopen

    def save(self, image_stream, image_content_type):
        ext = mimetypes.guess_extension(image_content_type)
        name = '{uuid}{ext}'.format(uuid=self._uuidgen(), ext=ext)
        image_path = os.path.join(self._storage_path, name)

        with self._fopen(image_path, 'wb') as image_file:
            while True:
                chunk = image_stream.read(self.__CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                
                image_file.write(chunk)

        return name
    
    def open(self, name):
        # Always validate intrusted input!
        if not self._IMAGE_NAME_PATTERN.match(name):
            raise IOError('File not found')
        
        image_path = os.path.join(self._storage_path, name)
        stream = self._fopen(image_path, 'rb')
        stream_len = os.path.getsize(image_path)

        return stream, stream_len