<div align="center">
	<h1>Oracle Online</h1>
	<p>
		A proof-of-concept for a digital version of the strategy card game
		<a href="https://oraclecardgame.com/">Oracle</a>! for the CSESoc
		Personal Projects Competition.
	</p>
</div>

- [`oracle.py`](oracle.py) contains the backend code.
- [`templates/`](templates) contains Jinja2 templates which are more or less
  HTML files.
- [`static/`](`static`) contains CSS and JS files.

To run the program, ensure you have
installed [Flask](https://flask.palletsprojects.com/en/2.1.x/installation/)
and [flask-sock](https://flask-sock.readthedocs.io/en/latest/quickstart.html),
then clone this repository.
After, to start the application, run

```sh
$ flask run
```

(Yes, I know that that starts the Werkzeug development server!)

Then, you can access the app at [localhost:5000/app](http://localhost:5000/app)!

Oracle Online is also hosted [here](https://thomasliang.pythonanywhere.com/app),
but because the application depends on unsecured WebSockets, you may need to
allow that in your browser settings before connecting.

There is also footage of the project uploaded to YouTube
[here](https://youtu.be/5uL0M107Y8s)!
