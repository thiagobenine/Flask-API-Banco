from flask import Flask, request, jsonify, session
from mongoengine import Document, StringField, FloatField, ListField, ReferenceField, DateTimeField, connect
from mongoengine.queryset.visitor import Q
from datetime import datetime, timedelta

class User(Document):
	name = StringField()
	cpf = StringField()
	account = StringField()
	agency = StringField()
	password = StringField()
	balance = FloatField()
	favorites = ListField(ReferenceField('self'))
	transactions = ListField(ReferenceField('Transaction'))

	def to_dict(self):
		return {
			"id": str(self.id),
			"name": self.name,
			"cpf": self.cpf,
			"account": self.account,
			"agency": self.agency,
			"balance": self.balance,
			"transactions": [transaction.to_dict() for transaction in self.transactions],
			"favorites": [favorite.name for favorite in self.favorites]
		}

class Transaction(Document):
	from_user = ReferenceField(User)
	to_user = ReferenceField(User)
	amount = FloatField()
	date = DateTimeField()
	label = StringField()

	def to_dict(self):
		return {
			"id": str(self.id),
			"from_user": str(self.from_user.name),
			"to_user": str(self.to_user.name) if self.to_user != None else "Unkown",
			"amount": self.amount,
			"date": int(self.date.timestamp()),
			"label": self.label
		}


app = Flask(__name__)
connect('bank2')

app.secret_key = "A0Zr98j/3yX R~XHH!jmN]LWX/,?RT"

def validate(data_in_request, correct_fields):
	for field in correct_fields:
		if not data_in_request.get(field):
			return "{field} is missing".format(field=field), False

	for data_field in data_in_request.keys():
		if data_field not in correct_fields:
			return "{data_field} is not necessary".format(data_field=data_field), False

	return "", True

def format_date(date):
	date_list_aux = date.replace("-",",").split(",")
	date_list_aux.extend([23,59,59])
	date_list_aux = [int(x) for x in date_list_aux]
	datetime_date = datetime(*date_list_aux)
	return datetime_date

def has_permission(func):
	def verification(**kwargs):
		if "user_id" in session:
			return func(**kwargs)
		else:
			return jsonify({"error": "forbidden", "message": "session not found"}), 403
	return verification

def is_valid_request_fields(*args):
	def is_valid_request(func):
		def validation():
			if not request.is_json:
				return jsonify({"error": "bad request", "message": "data is not in json format"}), 400

			data_in_request = request.get_json()

			correct_fields = args
			message, valid = validate(data_in_request, correct_fields)

			if not valid:
				return jsonify({"error": "bad request", "message": message}), 400

			return func(data_in_request)
		# validation.__name__ = func.__name__ ---> troquei por endpoint
		return validation
	return is_valid_request


@app.route('/users', methods=["POST"], endpoint='add_user')
@has_permission
@is_valid_request_fields("name", "cpf", "account", "agency", "password")
def add_user(data_in_request):

	users = User.objects(cpf = data_in_request["cpf"])
	if len(users) > 0:
		return jsonify({"error": "forbidden", "message": "user already exists"}), 403
	else:
		user = User(balance = 0, **data_in_request)
		user.save()

	return jsonify(user.to_dict()), 200

@app.route('/users')
def list_users():
	users = [user.to_dict() for user in User.objects()]
	return jsonify(users), 200

@app.route('/sessions', methods=["POST"], endpoint='add_session')
@is_valid_request_fields("cpf", "password")
def add_session(data_in_request):
	user = User.objects(cpf=data_in_request["cpf"], password=data_in_request["password"]).first()

	if user:
		session["user_id"] = str(user.id)
		return jsonify(user.to_dict()), 200
	else:
		return jsonify({"error": "not found", "message": "session not found"}), 404

@app.route('/sessions', endpoint='show_session')
@has_permission
def show_session(): #Tem que estar logado para ver a sessão atual ?
	if "user_id" in session:
		user = User.objects(id=session["user_id"]).first()
		return jsonify(user.to_dict()), 200
	else:
		return jsonify({"error": "not found", "message": "session not found"}), 404

@app.route('/balances', endpoint='show_balance')
@has_permission
def show_balance():
	user = User.objects(id=session["user_id"]).first()
	return jsonify({"balance": user.balance}), 200

@app.route('/extracts/<date_begin>/<date_end>/', endpoint='show_extract') #date_begin: yyyy-mm-dd
@app.route('/extracts/<date_begin>/', defaults={'date_end': datetime.now().strftime("%Y-%m-%d")}, endpoint='show_extract')
@app.route('/extracts/', defaults={'date_end': datetime.now().strftime("%Y-%m-%d"), 'date_begin': (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")},endpoint='show_extract')
@has_permission
def show_extract(date_begin, date_end):
	datetime_date_begin = format_date(date_begin)
	datetime_date_end = format_date(date_end)

	user = User.objects(id=session["user_id"]).first()

	if datetime_date_begin > datetime_date_end:
		return jsonify({"error": "bad request", "message": "date_begin should be lower than date_end"}), 400
	extract = Transaction.objects(Q(date__gte=datetime_date_begin) & Q(date__lte=datetime_date_end) & (Q(from_user = user) | Q(to_user = user)))
	if len(extract) > 0:
		transactions = [transaction.to_dict() for transaction in extract]
		return jsonify(transactions), 200
	else:
		return jsonify({"message":"no transactions"}), 200

@app.route('/transfers', methods=["POST"], endpoint='add_transfer')
@has_permission
@is_valid_request_fields("amount", "label", "cpf", "agency", "account")
def add_transfer(data_in_request):
	from_user = User.objects(id=session["user_id"]).first()
	to_user = User.objects(cpf=data_in_request["cpf"], agency=data_in_request["agency"], account=data_in_request["account"]).first()

	if to_user == None:
		return jsonify({"error": "not found", "message": "user does not exist"}), 404

	if from_user.balance >= float(data_in_request["amount"]):
		transaction_info = {
			"from_user" : from_user,
			"to_user" : to_user,
			"amount" : data_in_request["amount"],
			"label" : data_in_request["label"],
			"date" : datetime.now()
		}
		to_user.balance += float(data_in_request["amount"])
		from_user.balance -= float(data_in_request["amount"])
	else:
		return jsonify({"error": "forbidden", "message": "insufficient funds"}), 403

	favorites = [favorite.to_dict() for favorite in from_user.favorites]
	cpfs = [favorite["cpf"] for favorite in favorites]
	if to_user.cpf not in cpfs:
		from_user.favorites.append(to_user)


	transfer = Transaction(**transaction_info)
	transfer.save()
	from_user.transactions.append(transfer)
	from_user.save()
	to_user.transactions.append(transfer)
	to_user.save()
	return jsonify(transfer.to_dict()), 200

@app.route('/transfers/<date_begin>/<date_end>/', endpoint='list_transfers') #date_begin: yyyy-mm-dd
@app.route('/transfers/<date_begin>/', defaults={'date_end': datetime.now().strftime("%Y-%m-%d")}, endpoint='list_transfers')
@app.route('/transfers/', defaults={'date_end': datetime.now().strftime("%Y-%m-%d"), 'date_begin': (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")},endpoint='list_transfers')
@has_permission
def list_transfers(date_begin, date_end):
	datetime_date_begin = format_date(date_begin)
	datetime_date_end = format_date(date_end)

	user = User.objects(id=session["user_id"]).first()

	if datetime_date_begin > datetime_date_end:
		return jsonify({"error": "bad request", "message": "date_begin should be lower than date_end"}), 400

	transfers = Transaction.objects(Q(date__gte=datetime_date_begin) & Q(date__lte=datetime_date_end) & Q(from_user = user) & Q(to_user__ne = None))
	if len(transfers) > 0:
		transactions = [transaction.to_dict() for transaction in transfers]
		return jsonify(transactions), 200
	else:
		return jsonify({"message":"no transactions"}), 200

@app.route('/pay', methods=["POST"], endpoint='add_payment')
@has_permission
@is_valid_request_fields("code", "label", "amount")
def add_payment(data_in_request):
	from_user = User.objects(id=session["user_id"]).first()
	to_user = None

	if from_user.balance >= float(data_in_request["amount"]):
		transaction_info = {
			"from_user" : from_user,
			"to_user" : None,
			"amount" : data_in_request["amount"],
			"label" : data_in_request["label"],
			"date" : datetime.now()
		}
		from_user.balance -= float(data_in_request["amount"])
	else:
		return jsonify({"error": "forbidden", "message": "insufficient funds"}), 403

	payment = Transaction(**transaction_info)
	payment.save()
	from_user.transactions.append(payment)
	from_user.save()
	return jsonify(payment.to_dict()), 200

@app.route('/pay/<date_begin>/<date_end>/', endpoint='list_payments') #date_begin: yyyy-mm-dd
@app.route('/pay/<date_begin>/', defaults={'date_end': datetime.now().strftime("%Y-%m-%d")}, endpoint='list_payments')
@app.route('/pay/', defaults={'date_end': datetime.now().strftime("%Y-%m-%d"), 'date_begin': (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")},endpoint='list_payments')
@has_permission
def list_payments(date_begin, date_end):
	datetime_date_begin = format_date(date_begin)
	datetime_date_end = format_date(date_end)

	user = User.objects(id=session["user_id"]).first()

	if datetime_date_begin > datetime_date_end:
		return jsonify({"error": "bad request", "message": "date_begin should be lower than date_end"}), 400

	payments = Transaction.objects(Q(date__gte=datetime_date_begin) & Q(date__lte=datetime_date_end) & Q(from_user = user) & Q(to_user = None))
	if len(payments) > 0:
		transactions = [transaction.to_dict() for transaction in payments]
		return jsonify(transactions), 200
	else:
		return jsonify({"message":"no transactions"}), 200

@app.route('/favorites/', endpoint='list_favorites')
@has_permission
def list_favorites():
	user = User.objects(id=session["user_id"]).first()
	favorites = [favorite.to_dict() for favorite in user.favorites]

	if len(favorites) > 0:
		return jsonify(favorites), 200
	else:
		return jsonify({"message": "no favorites"}), 200

@app.route('/favorites/<cpf>/', endpoint='show_favorite')
@has_permission
def show_favorite(cpf):
	user = User.objects(id=session["user_id"]).first()
	print("***************************************************")
	favorite_candidate = User.objects(cpf = str(cpf)).first()
	print("***************************************************")


	favorites = [favorite.to_dict() for favorite in user.favorites]
	favorites_cpfs = [str(favorite["cpf"]) for favorite in favorites]

	if str(cpf) not in favorites_cpfs:
		return jsonify({"error":"not found", "message": "favorite not found"}), 404
	else:
		return jsonify(favorite_candidate.to_dict()), 200

@app.route('/favorites', methods=["POST"], endpoint='add_favorite')
@has_permission
@is_valid_request_fields("name", "agency", "account", "cpf")
def add_favorite(data_in_request):
	user = User.objects(id=session["user_id"]).first()
	favorite = User.objects(**data_in_request).first()

	favorites = [favorite.to_dict() for favorite in user.favorites]
	cpfs = [favorite["cpf"] for favorite in favorites]
	if favorite:
		if favorite.cpf not in cpfs:
			user.favorites.append(favorite)
			user.save()
			return jsonify(favorite.to_dict()), 200
		else:
			return jsonify({"error": "forbidden", "message": "user is already a favorite"}), 403
	else:
		return jsonify({"error": "not found", "message": "user does no exist"}), 404
