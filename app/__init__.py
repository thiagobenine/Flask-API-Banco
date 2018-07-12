from flask import Flask, request, jsonify, session
from mongoengine import Document, StringField,connect

class User(Document):
	name = StringField()
	cpf = StringField()
	account = StringField()
	agency = StringField()
	password = StringField()

	def to_dict(self):
		return {
			"id": str(self.id),
			"name": self.name,
			"cpf": self.cpf,
			"account": self.account,
			"agency": self.agency
		}

app = Flask(__name__)
connect('bank')

app.secret_key = "A0Zr98j/3yX R~XHH!jmN]LWX/,?RT"

def validate(data, fields):
	for field in fields:
		if not data.get(field):
			return "{field} is missing".format(field=field), False

	for field in data.keys():
		if field not in fields:
			return "{field} is not necessary".format(field=field), False

	return "", True

def has_permission(func):
	def verification():
		if session.get('user'):
			return func()
		else:
			return jsonify({"error": "forbidden", "message": "session not found"}), 403
	return verification

@app.route('/users', methods=["POST"])
@has_permission
def add_user():
	if not request.is_json:
		return jsonify({"error": "bad request", "message": "data is not in format json"}), 400

	data = request.get_json()

	fields = ["name", "cpf", "account", "agency", "password"]
	message, valid = validate(data, fields)

	if not valid:
		return jsonify({"error": "bad request", "message": message}), 400

	user = User(**data)
	user.save()

	return jsonify(user.to_dict()), 200

@app.route('/users')
def list_users():
	users = [user.to_dict() for user in User.objects()]
	return jsonify(users), 200

@app.route('/session', methods=["POST"])
def add_session():
	if not request.is_json:
		return jsonify({"error": "bad request", "message": "data is not in format json"}), 400

	data = request.get_json()

	fields = ["cpf", "password"]
	message, valid = validate(data, fields)

	if not valid:
		return jsonify({"error": "bad request", "message": message}), 400

	user = User.objects(cpf=data["cpf"], password=data["password"]).first()

	if user:
		session["user"] = True
		return jsonify(user.to_dict()), 200
	else:
		return jsonify({"error": "not found", "message": "session not found"}), 404
