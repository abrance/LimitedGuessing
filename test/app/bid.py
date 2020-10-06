from app.bid import FingerGuessCard


def test_FingerGuessCard():
    for i, v in enumerate(FingerGuessCard.points):
        c1 = FingerGuessCard()
        c1.set_point(v)
        c2 = FingerGuessCard()
        c2.set_point(v)
        r = FingerGuessCard.compare(c1.point, c2.point)
        assert r == 0

        c3 = FingerGuessCard()
        c3.set_point(v)
        c4 = FingerGuessCard()
        c4.set_point(c4.points[(i+1) % 3])
        r = FingerGuessCard.compare(c3.point, c4.point)
        assert r == c4.point


if __name__ == '__main__':
    test_FingerGuessCard()
