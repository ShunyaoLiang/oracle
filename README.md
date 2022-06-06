<div align="center">
	<h1>Oracle</h1>
	<p>
		A digital version of the strategy card game
		<a href="https://oraclecardgame.com/">Oracle</a>! for the CSESoc
		Personal Projects Competition.
	</p>
</div>

- [`oracle.py`](oracle.py) contains the backend code.
- [`templates/`](templates) contains Jinja2 templates which are more or less
  HTML files.
- [`static/`](`static`) contains CSS and JS files.

To run the program, ensure you have
[installed Flask](https://flask.palletsprojects.com/en/2.1.x/installation/) and
clone this repository.
Then, from within the repository run

```sh
$ export FLASK_APP=oracle
$ flask run
```
