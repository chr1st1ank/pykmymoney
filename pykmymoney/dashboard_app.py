import dash
import dash_core_components as dcc
import dash_html_components as html

from pykmymoney.kmmfile import KMMFile


class KMMDashboard():
    @staticmethod
    def df_to_htmltable(df, max_rows=None):
        if max_rows is None:
            max_rows = len(df)
        return html.Table(
            # Header
            [html.Tr([html.Th(col) for col in df.columns])] +

            # Body
            [html.Tr([
                html.Td(df.iloc[i][col]) for col in df.columns
            ]) for i in range(min(len(df), max_rows))]
        )

    def load_data(self, path):
        self.kmmfile = KMMFile.from_kmy(path)
        # TODO: Wertapierdepot-Werte hinzufügen
        assets_df = self.kmmfile.get_account("Anlagen:**", closed=False)\
            .query('last_balance != 0')\
            .sort_values(by='uri')\
            .rename({'uri': 'Konto', 'last_balance': 'Saldo', 'currency': 'Währung'}, axis=1)\
            [['Konto', 'Saldo', 'Währung']]
            # [['uri', 'type_id', 'last_balance', 'currency']]
        assets_df['Konto'] = assets_df['Konto'].str.split(':').apply(lambda s: s[-1])
        liabilities_df = self.kmmfile.get_account("Anlagen:**", closed=False)\
            .query('last_balance != 0')\
            .sort_values(by='uri')\
            .rename({'uri': 'Konto', 'last_balance': 'Saldo', 'currency': 'Währung'}, axis=1)\
            [['Konto', 'Saldo', 'Währung']]
            # [['uri', 'type_id', 'last_balance', 'currency']]
        assets_df['Konto'] = assets_df['Konto'].str.split(':').apply(lambda s: s[-1])


        self.app = dash.Dash(external_stylesheets=['https://codepen.io/chriddyp/pen/bWLwgP.css'])
        colors = {
            'background': '#FFFFFF',
            'text': '#333333'
        }
        # app.layout = html.Div(style={'backgroundColor': colors['background']}, children=[
        self.app.layout = html.Div(children=[
            html.H1(
                children='Finanzübersicht',
                style={
                    'textAlign': 'center',
                    'color': colors['text']
                }
            ),
            html.H2(
                children='Kontenüberblick'
            ),
            self.df_to_htmltable(assets_df),
            self.df_to_htmltable(self.kmmfile.get_account("Verbindlichkeiten:**", closed=False).sort_values(by='uri')[
                                     ['uri', 'type_id', 'last_balance', 'currency']
                                 ]),
            html.Div(children='Dash: A web application framework for Python.', style={
                'textAlign': 'center',
                'color': colors['text']
            }),
            dcc.Graph(
                id='Graph1',
                figure={
                    'data': [
                        {'x': [1, 2, 3], 'y': [4, 1, 2], 'type': 'bar', 'name': 'SF'},
                        {'x': [1, 2, 3], 'y': [2, 4, 5], 'type': 'bar', 'name': u'Montréal'},
                    ],
                    'layout': {
                        'plot_bgcolor': colors['background'],
                        'paper_bgcolor': colors['background'],
                        'font': {
                            'color': colors['text']
                        }
                    }
                }
            )
            # TODO Scatterplot Frequency vs Value of expenses
            # see https://www.datacamp.com/community/tutorials/learn-build-dash-python
        ])

if __name__ == '__main__':
    import os
    db = KMMDashboard()
    db.load_data(os.environ['KMM_FILE'])
    db.app.run_server(debug=True)
