class KrishaParser:
    def __init__(self, listings):
        self.listings = listings

    def parse(self):
        parsed_data = []
        for listing in self.listings:
            parsed_data.append(self._parse_listing(listing))
        return parsed_data

    def _parse_listing(self, listing):
        # Implement listing parsing logic here
        return {
            'title': listing.get('title', ''),
            'price': listing.get('price', ''),
            'location': listing.get('location', ''),
            'description': listing.get('description', ''),
        }
