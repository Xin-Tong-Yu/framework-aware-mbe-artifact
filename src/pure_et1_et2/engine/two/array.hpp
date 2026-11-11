#ifndef XC_ARRAY_HPP
#define XC_ARRAY_HPP

class XCArray_t {
private:
    int32_t *vSet = nullptr;
    int32_t *pSet = nullptr;
    int32_t sz = 0;

public:
    int32_t x, c, r, c_;

    XCArray_t() = default;

    ~XCArray_t() {
        delete [] vSet;
        delete [] pSet;
    }

    void resize(int32_t size) {
        sz = size;
        c = 0;
        x = 0;
        r = size;
        vSet = new int32_t[size];
        pSet = new int32_t[size];

        for (int32_t i = 0; i < size; i++) {
            vSet[i] = pSet[i] = i;
        }
    }

    void reset() {
        c = 0;
        x = 0;
        r = sz;
        c_ = 0;
    }

    void swapByPos(int32_t i, int32_t j) {
        std::swap(vSet[i], vSet[j]);
        std::swap(pSet[vSet[i]], pSet[vSet[j]]);
    }

    int32_t operator [] (int32_t i) {
        return vSet[i];
    }

    int32_t pos(int32_t v) {
        return pSet[v];
    }

    bool CIsEmpty() {
        return c == r;
    }

    bool XIsEmpty() {
        return x == c;
    }

    int32_t cSize() {
        return r - c;
    }

    int32_t xSize() {
        return c - x;
    }

    int32_t cPrimeSize() {
        return c_ - c;
    }

    int32_t cRemainSize() {
        return r - c_;
    }

    int32_t *begin() {
        return vSet;
    }

    void print() {
        printf("X:");
        for (int32_t i = x; i < c; i++) {
            printf("%u ", vSet[i]);
        }
        printf("C:");
        for (int32_t i = c; i < r; i++) {
            printf("%u ", vSet[i]);
        }
        printf("R:");
        for (int32_t i = r; i < sz; i++) {
            printf("%u ", vSet[i]);
        }
    }
};

#endif