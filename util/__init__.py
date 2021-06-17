from datetime import datetime, timedelta


def get_jkt_timezone():
    utc = datetime.utcnow()
    return utc + timedelta(hours=7)


def row2dict(row, hidden_column=[]):
    d = {}
    for column in row.__table__.columns:
        if column.name not in hidden_column:
            d[column.name] = str(getattr(row, column.name))

    return d
