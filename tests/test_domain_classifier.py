from app.services.domain_classifier import DomainClassifier

class TestDomainClassifier:
    def test_domain_classification(self):
        classifier = DomainClassifier()
        result = classifier.classify_domain("https://dichvucong.gov.vn/p/home/dvc-trang-chu.html")
        assert "government" in result['labels']