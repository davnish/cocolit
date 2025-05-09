from sqlmodel import create_engine



host = 'localhost'
database = 'coconut_db'
user = 'postgres'
password = 'postgres'

connection_string = f"postgresql://{user}:{password}@{host}/{database}"

engine = create_engine(connection_string)