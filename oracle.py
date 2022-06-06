from flask import Flask, redirect, render_template, url_for

# Create our Flask application.
app = Flask(__name__)

@app.route('/game')
def get_game():
    # Respond with the page.
    return render_template('game.html')

@app.route('/')
def redirect_to_game():
    # Since, for now, there is only one page, redirect there.
    return redirect(url_for('get_game'))
