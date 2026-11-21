# Scraper worker

This is a Python selenium scraper worker that scrapes multiple Pharamcy websites and checks for products availability and fills up the carts of those websites.
So it not only scrapes the websites, but also interacts with them as if a user is trying to buy pharmacy items.
The goal is to have a list of desired items to be bought, iterate through every list item and add it to the cart of the cheapest pharmacy distributor

## Critical ordering invariants

- Never buy a different product as a fallback for the requested product.
- Never increase the quantity of product `Y` because product `X` was matched incorrectly.
- If the scraper is not confident that the distributor product is the intended product, the safe outcome is `unbought`, not `bought`.
- False negatives are acceptable here; false positives are not. A missed purchase can be retried, but a wrong purchase creates an incorrect order and over-orders inventory.


## Start the app

Start it as a local process:
```bash
make run
```

Start it as a docker container:

```bash
make docker-build
make docker-run
make docker-stop
```
