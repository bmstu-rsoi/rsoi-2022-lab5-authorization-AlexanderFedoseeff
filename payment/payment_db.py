import psycopg2
from psycopg2 import Error
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

class PaymentDB:
    def __init__(self):
        self.initDB()
        self.DB_URL = "postgresql://postgres:postgres@postgres:5432/payments"
        if not self.check_existing_table_payment():
            self.create_table_payment()

    def initDB(self):
        connection = psycopg2.connect(
                            database="postgres",
                            user='postgres',
                            password='postgres',
                            host='postgres',
                            port= '5432')
        connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = connection.cursor()
        try:
            cursor.execute(""" CREATE DATABASE payments """)
            connection.commit()
        except (Exception, Error) as error:
            print("Ошибка при работе с PostgreSQL", error)
        finally:
            cursor.close()
            connection.close()
            
    def check_existing_table_payment(self):
        connection = psycopg2.connect(self.DB_URL)
        cursor = connection.cursor()
        cursor.execute("""SELECT table_name FROM information_schema.tables
               WHERE table_schema = 'public'""")
        for table in cursor.fetchall():
            if table[0] == "payment":
                cursor.close()
                return True
        cursor.close()
        connection.close()
        return False


    def create_table_payment(self):
        q = '''
            CREATE TABLE payment
            (
                id          SERIAL PRIMARY KEY,
                payment_uid uuid        NOT NULL,
                status      VARCHAR(20) NOT NULL
                    CHECK (status IN ('PAID', 'CANCELED')),
                price       INT         NOT NULL
            );
            '''
        connection = psycopg2.connect(self.DB_URL)
        cursor = connection.cursor()
        cursor.execute(q)
        connection.commit()
        cursor.close()
        connection.close()

    def get_payment(self, paymentUid):
        result = list()
        try:
            connection = psycopg2.connect(self.DB_URL)
            cursor = connection.cursor()
            cursor.execute(''' SELECT status, price FROM payment WHERE payment_uid = %s; ''', (paymentUid,))
            record = cursor.fetchall()
            for i in record:
                i = list(i)
                result.append({"status": i[0], "price": i[1]})
        except (Exception, Error) as error:
            print("Ошибка при работе с PostgreSQL", error)
        finally:
            if connection:
                cursor.close()
                connection.close()
                print("Соединение с PostgreSQL закрыто")
        return result

    def post_payment(self, uiid, price):
        result = list()
        try:
            connection = psycopg2.connect(self.DB_URL)
            cursor = connection.cursor()
            q = '''
                INSERT INTO payment
                (
                    payment_uid,
                    status,
                    price
                )
                VALUES 
                (
                    %s,
                    %s,
                    %s
                );
                '''
            cursor.execute(q, (uiid, 'PAID', price))
            connection.commit()
            result.append({'payment_uid': uiid, 'status': 'PAID'})
        except (Exception, Error) as error:
            print("Ошибка при работе с PostgreSQL", error)
            result.append({'payment_uid': uiid, 'status': 'PAID'})
        finally:
            if connection:
                cursor.close()
                connection.close()
                print("Соединение с PostgreSQL закрыто")
        return result

    def cancel_payment(self, paymentUid):
        result = False
        try:
            connection = psycopg2.connect(self.DB_URL)
            cursor = connection.cursor()
            q = ''' UPDATE payment SET status = %s WHERE payment_uid = %s; '''
            cursor.execute(q, ('CANCELED', paymentUid))
            connection.commit()
            if cursor.rowcount > 0:
                result = True
        except (Exception, Error) as error:
            print("Ошибка при работе с PostgreSQL", error)
        finally:
            if connection:
                cursor.close()
                connection.close()
                print("Соединение с PostgreSQL закрыто")
        return result