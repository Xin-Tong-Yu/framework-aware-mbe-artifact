#ifndef HEAP_H
#define HEAP_H

#include <cstdlib>
#include <cstdio>
#include <cmath>
#include <cstring>
#include <string>
#include <vector>
#include <algorithm>
#include <iostream>
#include <cassert>

class Heap_t {
private:
	int32_t n; // number vertices
	int32_t key_cap; // the maximum allowed key value

	int32_t max_key; // possible max key
	int32_t min_key; // possible min key

	int32_t *keys; // keys of vertices
			  // keys[i] > key_cap if vertex i is not in the data structure

	int32_t *heads; // head of doubly-linked list for a specific weight
	int32_t *pres; // pre for doubly-linked list
	int32_t *nexts; // next for doubly-linked list

public:
	Heap_t(int32_t _n, int32_t _key_cap) {
		n = _n;
		key_cap = _key_cap;

		min_key = key_cap;
		max_key = 0;

		heads = keys = pres = nexts = nullptr;
	}
	~Heap_t() {
		if(heads != nullptr) {
			delete[] heads;
			heads = nullptr;
		}
		if(pres != nullptr) {
			delete[] pres;
			pres = nullptr;
		}
		if(nexts != nullptr) {
			delete[] nexts;
			nexts = nullptr;
		}
		if(keys != nullptr) {
			delete[] keys;
			keys = nullptr;
		}
	}

	void reserve(int32_t n, int32_t _key_cap) {
        if (keys == nullptr) keys = new int32_t[n];
        if (pres == nullptr) pres = new int32_t[n];
        if (nexts == nullptr) nexts = new int32_t[n];
        if (heads == nullptr) heads = new int32_t[key_cap + 1];
    }

	// initialize the data structure by (id, key) pairs
	// _n is the number of pairs, _key_cap is the maximum possible key value
	void init(int32_t _n, int32_t _key_cap, int32_t *_ids, int32_t *_keys) {
        n = _n;
        key_cap = _key_cap;
        if (keys == nullptr) keys = new int32_t[n];
        if (pres == nullptr) pres = new int32_t[n];
        if (nexts == nullptr) nexts = new int32_t[n];
        if (heads == nullptr) heads = new int32_t[key_cap + 1];
        assert(_key_cap <= key_cap);
        min_key = _key_cap;
        max_key = 0;
        for (int32_t i = 0; i <= _key_cap; i++) heads[i] = n;

        for (int32_t i = 0; i < _n; i++) insert(_ids[i], _keys[i]);
    }

	// insert (id, key) pair into the data structure
	void insert(int32_t id, int32_t key) {
        assert(id < n);
        assert(key <= key_cap);

        keys[id] = key;
        pres[id] = n;
        nexts[id] = heads[key];
        if (heads[key] != n) pres[heads[key]] = id;
        heads[key] = id;

        if (key < min_key) min_key = key;
        if (key > max_key) max_key = key;
    }

	// remove a vertex from the data structure
	int32_t remove(int32_t id) {
        assert(keys[id] <= max_key);
        if (pres[id] == n) {
            assert(heads[keys[id]] == id);
            heads[keys[id]] = nexts[id];
            if (nexts[id] != n) pres[nexts[id]] = n;
        } else {
            int32_t pid = pres[id];
            nexts[pid] = nexts[id];
            if (nexts[id] != n) pres[nexts[id]] = pid;
        }

        return keys[id];
    }

	int32_t get_n() {
        return n;
    }

	int32_t get_key_cap() {
        return key_cap;
    }

	int32_t get_key(int32_t id) {
        return keys[id];
    }

	void get_ids(std::vector<int32_t> &ids) {
        ids.clear();
        tighten();
        for (int32_t i = min_key; i <= max_key; i++) {
            for (int32_t id = heads[i]; id != n; id = nexts[id]) {
                ids.push_back(id);
            }
        }
    }

	void get_ids_keys(std::vector<int32_t> &ids, std::vector<int32_t> &_keys) {
        ids.clear();
        _keys.clear();
        tighten();
        for (int32_t i = min_key; i <= max_key; i++) {
            for (int32_t id = heads[i]; id != n; id = nexts[id]) {
                ids.push_back(id);
                _keys.push_back(id);
            }
        }
    }

	bool empty() {
        tighten();
        return min_key > max_key;
    }

	int32_t size() {
        tighten();
        int32_t res = 0;
        for (int32_t i = min_key; i <= max_key; i++) for (int32_t id = heads[i]; id != n; id = nexts[id]) ++res;
        return res;
    }

	// get the (id,key) pair with the maximum key value; return true if success, return false otherwise
	bool get_max(int32_t &id, int32_t &key) {
        if (empty()) return false;

        id = heads[max_key];
        key = max_key;
        assert(keys[id] == key);
        return true;
    }

	// pop the (id,key) pair with the maximum key value; return true if success, return false otherwise
	bool pop_max(int32_t &id, int32_t &key) {
        if (empty()) return false;

        id = heads[max_key];
        key = max_key;
        assert(keys[id] == key);

        heads[max_key] = nexts[id];
        if (heads[max_key] != n) pres[heads[max_key]] = n;

        tighten();
        return true;
    }

	// get the (id,key) pair with the minimum key value; return true if success, return false otherwise
	bool get_min(int32_t &id, int32_t &key) {
        if (empty()) return false;

        id = heads[min_key];
        key = min_key;
        assert(keys[id] == key);

        return true;
    }

	// pop the (id,key) pair with the minimum key value; return true if success, return false otherwise
	bool pop_min(int32_t &id, int32_t &key) {
        if (empty()) return false;

        id = heads[min_key];
        key = min_key;

        assert(keys[id] == key);
        keys[id] = 0;

        heads[min_key] = nexts[id];
        if (heads[min_key] != n) pres[heads[min_key]] = n;

        tighten();
        return true;
    }

	// increment the key of vertex id by inc
	int32_t increment(int32_t id, int32_t inc = 1) {
        assert(keys[id] + inc <= key_cap);

        int32_t new_key = keys[id] + inc;

        remove(id);
        insert(id, new_key);

        return new_key;
    }

	// decrement the key of vertex id by dec
	int32_t decrement(int32_t id, int32_t dec = 1) {
        // assert(keys[id] >= dec);
        if (keys[id] < dec) return 0;
        int32_t new_key = keys[id] - dec;

        remove(id);
        insert(id, new_key);

        tighten();
        return new_key;
    }

private:
	void tighten() {
        while (min_key <= max_key && heads[min_key] == n) ++min_key;
        while (min_key <= max_key && heads[max_key] == n) --max_key;
    }
};

#endif