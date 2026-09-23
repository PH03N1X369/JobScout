"""Company career boards read through their hiring platform's public job-board API.

These feeds are published by the companies themselves for exactly this kind of
reuse, need no API key, and include on-site roles, which the remote-job
boards in sources.py don't. Boards are grouped by the country whose jobs we
pull from them; a board is only queried when a search's location is in that
country, and only that country's jobs are kept.

To add a company, find its careers page URL:
  boards.greenhouse.io/<slug>  or  job-boards.greenhouse.io/<slug>  -> ("greenhouse", "<slug>", "Name")
  jobs.lever.co/<slug>                                              -> ("lever", "<slug>", "Name")
  jobs.ashbyhq.com/<slug>                                           -> ("ashby", "<slug>", "Name")
"""

COMPANY_BOARDS = {
    "IN": [
        # Greenhouse
        ("greenhouse", "databricks", "Databricks"),
        ("greenhouse", "okta", "Okta"),
        ("greenhouse", "mongodb", "MongoDB"),
        ("greenhouse", "highradius", "HighRadius"),
        ("greenhouse", "stripe", "Stripe"),
        ("greenhouse", "inmobi", "InMobi"),
        ("greenhouse", "rubrik", "Rubrik"),
        ("greenhouse", "zenoti", "Zenoti"),
        ("greenhouse", "netskope", "Netskope"),
        ("greenhouse", "zoominfo", "ZoomInfo"),
        ("greenhouse", "twilio", "Twilio"),
        ("greenhouse", "druva", "Druva"),
        ("greenhouse", "agoda", "Agoda"),
        ("greenhouse", "airbnb", "Airbnb"),
        ("greenhouse", "groww", "Groww"),
        ("greenhouse", "glance", "Glance"),
        ("greenhouse", "gitlab", "GitLab"),
        ("greenhouse", "toast", "Toast"),
        ("greenhouse", "hackerrank", "HackerRank"),
        ("greenhouse", "elastic", "Elastic"),
        ("greenhouse", "coinbase", "Coinbase"),
        ("greenhouse", "datadog", "Datadog"),
        ("greenhouse", "samsara", "Samsara"),
        ("greenhouse", "sumologic", "Sumo Logic"),
        ("greenhouse", "bitgo", "BitGo"),
        ("greenhouse", "figma", "Figma"),
        # Lever
        ("lever", "paytm", "Paytm"),
        ("lever", "meesho", "Meesho"),
        ("lever", "hevodata", "Hevo Data"),
        ("lever", "zeta", "Zeta"),
        ("lever", "mindtickle", "Mindtickle"),
        ("lever", "fampay", "FamPay"),
        ("lever", "cred", "CRED"),
        ("lever", "binance", "Binance"),
        ("lever", "pocketfm", "Pocket FM"),
        # Ashby
        ("ashby", "tekion", "Tekion"),
        ("ashby", "sarvam", "Sarvam AI"),
        ("ashby", "atlan", "Atlan"),
        ("ashby", "notion", "Notion"),
    ],
}
