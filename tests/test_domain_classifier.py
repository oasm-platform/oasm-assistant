from app.services.domain_classifier import DomainClassifier

class TestDomainClassifier:
    def test_domain_classification(self):
        classifier = DomainClassifier()
        result = classifier.classify_domain("https://www.hackerone.com/")
        assert "Technology" in result['labels']